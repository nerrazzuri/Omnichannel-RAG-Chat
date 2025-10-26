"""
RAG service with hybrid retrieval (BM25 + dense vectors) and RRF fusion,
augmented with OpenAI chat generation using a strict prompt to avoid
hallucinations.
"""
from typing import List, Dict, Any, Optional, Tuple
import logging
import time
import difflib
from datetime import datetime
from collections import defaultdict, Counter as ColCounter
import math
import re
import os
import json
import urllib.parse
import urllib.request
from sqlalchemy.orm import Session
from shared.database.models import KnowledgeChunk, Document, KnowledgeBase
from shared.cache.redis import redis_cache
from openai import OpenAI
from shared.vector.qdrant import qdrant_service
from shared.config.tuning import retrieval
from shared.database.models import Document as DbDocument, KnowledgeChunk as DbChunk, KnowledgeBase as DbKB
from .reranker_service import get_reranker, RerankingResult
from shared.config.tuning import reranker_config
from prometheus_client import Counter as PromCounter, Histogram

logger = logging.getLogger(__name__)
 
# 添加监控指标
RERANK_REQUESTS = PromCounter('rag_rerank_requests_total', 'Total reranking requests')
RERANK_LATENCY = Histogram('rag_rerank_latency_seconds', 'Reranking latency')
RERANK_ERRORS = PromCounter('rag_rerank_errors_total', 'Reranking errors')

class StandardBM25:
    def __init__(self, corpus: List[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.doc_count = len(corpus)
        self.doc_len: List[int] = []
        self.doc_freqs: List[ColCounter] = []
        self.vocab: List[str] = []
        self.idf: Dict[str, float] = {}
        self.avgdl = (sum(len(doc.split()) for doc in corpus) / self.doc_count) if self.doc_count else 0.0
        self._build_stats()

    def _build_stats(self) -> None:
        vocab_set = set()
        for doc in self.corpus:
            words = doc.lower().split()
            self.doc_len.append(len(words))
            cnt = ColCounter(words)
            self.doc_freqs.append(cnt)
            vocab_set.update(cnt.keys())
        self.vocab = list(vocab_set)
        self._compute_idf()

    def _compute_idf(self) -> None:
        N = max(1, self.doc_count)
        for term in self.vocab:
            n = sum(1 for df in self.doc_freqs if term in df)
            # Standard BM25 IDF
            self.idf[term] = math.log((N - n + 0.5) / (n + 0.5))

    def score(self, query: str) -> List[float]:
        if not self.corpus:
            return []
        q_terms = query.lower().split()
        scores: List[float] = []
        for i, df in enumerate(self.doc_freqs):
            score = 0.0
            dl = self.doc_len[i] if i < len(self.doc_len) else 0
            for qt in q_terms:
                if qt not in df:
                    continue
                tf = df[qt]
                idf = self.idf.get(qt, 0.0)
                denom = tf + self.k1 * (1 - self.b + self.b * (dl / max(1.0, self.avgdl)))
                score += idf * ((tf * (self.k1 + 1)) / max(1e-9, denom))
            scores.append(score)
        return scores


class HybridRetriever:
    def __init__(self):
        self.corpus = []
        self.bm25: Optional[StandardBM25] = None

    def index(self, documents: List[str]) -> None:
        self.corpus = documents[:]
        self.bm25 = StandardBM25(self.corpus)

    def keyword_search(self, query: str, top_k: int = 5) -> List[int]:
        if not self.bm25:
            self.bm25 = StandardBM25(self.corpus)
        scores = self.bm25.score(query)
        
        # Boost scores for exact query matches
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        for i, doc in enumerate(self.corpus):
            doc_lower = doc.lower()
            # Exact substring match gets highest boost
            if query_lower in doc_lower:
                scores[i] += 10.0
            # All query terms present gets medium boost
            elif all(term in doc_lower for term in query_terms):
                scores[i] += 5.0
            # Partial term matches get small boost
            else:
                matching_terms = sum(1 for term in query_terms if term in doc_lower)
                if matching_terms > 0:
                    scores[i] += matching_terms * 1.0
        
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [i for i, _ in ranked[:top_k]]

    def dense_search(self, query: str, top_k: int = 5) -> List[int]:
        """Temporary dense search fallback.

        Uses keyword_search rankings to avoid errors when a true vector search
        implementation is unavailable in this context.
        """
        return self.keyword_search(query, top_k=top_k)

    def rrf_fuse(self, lists: List[List[int]], k: int = 60, top_k: int = 5) -> List[int]:
        """Deprecated: Use RAGService._fuse_candidates for a single fusion policy.
        Kept for backwards compatibility in simple retrieval-only paths.
        """
        ranks: Dict[int, float] = defaultdict(float)
        for idx_list in lists:
            for rank, doc_id in enumerate(idx_list, start=1):
                ranks[doc_id] += 1.0 / (k + rank)
        fused = sorted(ranks.items(), key=lambda x: x[1], reverse=True)
        return [i for i, _ in fused[:top_k]]

    def retrieve(self, query: str, top_k: int = 6) -> List[str]:
        if not self.corpus:
            return []
        
        # Check for exact matches first
        exact_matches = []
        query_lower = query.lower()
        for i, doc in enumerate(self.corpus):
            if query_lower in doc.lower():
                exact_matches.append(i)
        
        # If we have exact matches, prioritize them
        if exact_matches:
            # Still do hybrid search but boost exact matches
            kw = self.keyword_search(query, top_k=max(top_k * 2, 15))
            dn = self.dense_search(query, top_k=max(top_k, 10))
            
            # Ensure exact matches appear in both lists for higher RRF score
            kw_set = set(kw)
            dn_set = set(dn)
            for match_id in exact_matches[:3]:  # Add top 3 exact matches
                if match_id not in kw_set:
                    kw.insert(0, match_id)
                if match_id not in dn_set:
                    dn.insert(0, match_id)
            
            fused_ids = self.rrf_fuse([kw, dn], top_k=top_k)
        else:
            # Standard hybrid retrieval
            kw = self.keyword_search(query, top_k=max(top_k, 10))
            dn = self.dense_search(query, top_k=top_k)
            fused_ids = self.rrf_fuse([kw, dn], top_k=top_k)
        
        return [self.corpus[i] for i in fused_ids]


class RAGService:
    def __init__(self):
        self.retriever = HybridRetriever()
        self.cache_ttl_seconds = 300
        # OpenAI client for generation (optional if API key not provided)
        api_key = os.getenv("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=api_key) if api_key else None
        # Default models and parameters aligned with samples
        self.chat_model = os.getenv("RAG_CHAT_MODEL", "gpt-5-mini")
        self.chat_temperature = float(os.getenv("RAG_CHAT_TEMPERATURE", "0.3"))
        self.reranker = get_reranker()
        self.reranker_enabled = reranker_config.enabled
        # Strict prompt to keep answers grounded
        self.prompt_template = (
            "You are a professional corporate assistant. Your name is Omni.\n\n"
            "You receive CONTEXT that has already been interpreted into natural language.\n"
            "Answer the QUESTION concisely in human language. Do NOT quote raw field labels or key:value pairs.\n"
            "Prefer short, direct answers (yes/no, a single date/number, or 1-2 sentences) unless more detail is clearly required.\n\n"
            "If the context truly lacks the relevant information, reply exactly with: \n"
            "\"I don’t have that information in the current database.\"\n\n"
            "Examples:\n"
            "- If marital status is married, answer: 'Yes, <Name> is married.'\n"
            "- If the hire date is 2015-06-01, answer: 'June 1, 2015.'\n"
            "- If salary is $90,000, answer: '$90,000.'\n\n"
            "Always include brief source citations at the end.\n\n"
            "---\nCONTEXT:\n{context}\n---\nQUESTION:\n{question}\n---\nAnswer:"
        )
        self.no_info_text = "I don’t have that information in the current database."
        # Ensure state reflects config
        self.reranker = get_reranker()
        self.reranker_enabled = reranker_config.enabled

    def load_documents(self, docs: List[str]) -> None:
        self.retriever.index(docs)

    def plan(self, query: str) -> Dict[str, Any]:
        """Ask the LLM to propose a retrieval/answer strategy so AI decides the logic."""
        default_plan: Dict[str, Any] = {
            "task_type": "generic",
            "entity": None,
            "field": None,
            "list": None,
            "chapter": None,
            "aggregation": None,
        }
        if not self.openai_client:
            return default_plan
        try:
            planner_prompt = (
                "You are a retrieval planner. Analyze the USER question and output a strict JSON object with fields: "
                "task_type (one of: generic, tabular_field, tabular_aggregate, policy_summary, list_request, chapter_nav), "
                "entity (string or null), field (string or null), list (object with mode and n or null), chapter (object with base or null), "
                "aggregation (object or null). aggregation supports: op (sum|avg|count|min|max|distinct_count), field (string), sheet (string or null), "
                "filters (array of {column,value,op}), where op in [eq,ne,gt,gte,lt,lte,contains], group_by (array of strings or null), "
                "date_field (string or null), time_range (object or null with forms: {type:'year',value:'2014'} | {type:'between',start:'2014-01-01',end:'2014-12-31'} | {type:'quarter',value:'Q1 2014'}). "
                "Respond with JSON ONLY."
            )
            msg = [
                {"role": "system", "content": planner_prompt},
                {"role": "user", "content": query},
            ]
            completion = self.openai_client.chat.completions.create(
                model=os.getenv("RAG_PLANNER_MODEL", self.chat_model),
                temperature=0,
                messages=msg,
            )
            raw = (completion.choices[0].message.content or "").strip()
            import json
            plan = json.loads(raw)
            if isinstance(plan, dict):
                # Shallow-merge with defaults
                out = default_plan.copy()
                out.update({k: plan.get(k) for k in out.keys() if k in plan})
                return out
            return default_plan
        except Exception:
            return default_plan

    # Unified fusion policy: configurable RRF with weights
    def _fuse_candidates(
        self,
        bm25_texts: List[str],
        dense_hits_rich: List[Dict[str, Any]],
        query: str,
        field_value_hits_rich: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        # Build candidate list
        candidates = bm25_texts[:]
        vec_map: Dict[str, float] = {}
        for h in (dense_hits_rich or []):
            t = (h.get('content') or '')
            if not t:
                continue
            vec_map[t] = max(vec_map.get(t, 0.0), float(h.get('score') or 0.0))
            if t not in candidates:
                candidates.append(t)
        fv_map: Dict[str, float] = {}
        for h in (field_value_hits_rich or []):
            t = (h.get('content') or '')
            if not t:
                continue
            fv_map[t] = max(fv_map.get(t, 0.0), float(h.get('score') or 0.0))
            if t not in candidates:
                candidates.append(t)
        if not candidates:
            return []
        # BM25 ranks
        bm = StandardBM25(candidates)
        bm_scores = bm.score(query)
        ranked_bm = sorted([(s, i) for i, s in enumerate(bm_scores)], key=lambda x: x[0], reverse=True)
        bm25_ranking: Dict[str, int] = {}
        for rnk, (_s, idx) in enumerate(ranked_bm):
            bm25_ranking[candidates[idx]] = rnk
        # Dense ranks
        dense_ranking: Dict[str, int] = {}
        if vec_map:
            sorted_dense = sorted(vec_map.items(), key=lambda x: x[1], reverse=True)
            for rnk, (t, _sc) in enumerate(sorted_dense):
                dense_ranking[t] = rnk
        # Field-value ranks
        fv_ranking: Dict[str, int] = {}
        if fv_map:
            sorted_fv = sorted(fv_map.items(), key=lambda x: x[1], reverse=True)
            for rnk, (t, _sc) in enumerate(sorted_fv):
                fv_ranking[t] = rnk
        # RRF with weights from config
        k_rrf = getattr(retrieval, 'rrf_k', 60)
        w_bm = getattr(retrieval, 'rrf_w_bm25', 0.4)
        w_vec = getattr(retrieval, 'rrf_w_dense', 0.5)
        w_fv = getattr(retrieval, 'rrf_w_field_values', 0.6)
        scores: Dict[str, float] = {}
        for t in candidates:
            r_bm = bm25_ranking.get(t)
            r_vec = dense_ranking.get(t)
            r_fv = fv_ranking.get(t)
            s = 0.0
            if r_bm is not None:
                s += w_bm * (1.0 / (k_rrf + r_bm))
            if r_vec is not None:
                s += w_vec * (1.0 / (k_rrf + r_vec))
            if r_fv is not None:
                s += w_fv * (1.0 / (k_rrf + r_fv))
            scores[t] = s
        ordered = [t for t, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
        return ordered

    def _prepare_candidates(
        self,
        query: str,
        preselected_contexts: Optional[List[str]],
        tenant_id: str,
        db: Optional[Session],
        bm25_query: Optional[str] = None,
    ) -> Tuple[List[str], List[Dict[str, Any]], Optional[List[float]], Dict[str, Dict[str, str]], List[str], List[Dict[str, Any]]]:
        contexts: List[str] = []
        vector_hits_rich: List[Dict[str, Any]] = []
        emb_avg: Optional[List[float]] = None
        content_to_row: Dict[str, Dict[str, str]] = {}
        stitched_texts: List[str] = []
        field_value_hits_rich: List[Dict[str, Any]] = []

        if db is not None:
            try:
                emb_avg = self._embed_queries_avg(query)
            except Exception:
                emb_avg = None
            try:
                vector_hits_rich = self._qdrant_contexts_rich(query, tenant_id=tenant_id, top_k=retrieval.vector_top_k, emb_override=emb_avg)
            except Exception:
                vector_hits_rich = []
            try:
                field_value_hits_rich = self._qdrant_field_values_rich(query, tenant_id=tenant_id, top_k=getattr(retrieval, 'field_value_top_k', 8), emb_override=emb_avg)
            except Exception:
                field_value_hits_rich = []
            # Build BM25 over tenant chunk corpus with IDs for true fusion
            try:
                q = (
                    db.query(KnowledgeChunk, Document, KnowledgeBase)
                    .join(Document, KnowledgeChunk.document_id == Document.id)
                    .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
                    .filter(KnowledgeBase.tenant_id == tenant_id)
                )
                tenant_pairs = q.limit(2000).all()
                id_to_content: Dict[str, str] = {}
                content_to_row_local: Dict[str, Dict[str, str]] = {}
                corpus_texts: List[str] = []
                idx_to_id: List[str] = []
                sig_to_id: Dict[str, str] = {}
                for kc, _doc, _kb in tenant_pairs:
                    c = getattr(kc, 'content', None)
                    kid = str(getattr(kc, 'id', ''))
                    if isinstance(c, str) and c.strip() and kid:
                        id_to_content[kid] = c
                        idx_to_id.append(kid)
                        corpus_texts.append(c)
                        sig_to_id[c[:200].lower()] = kid
                        try:
                            meta = getattr(kc, 'meta', {}) or {}
                            rowm = meta.get('row') if isinstance(meta, dict) else None
                            if isinstance(rowm, dict) and rowm:
                                content_to_row_local[c] = {str(k): str(v) for k, v in rowm.items() if v is not None}
                        except Exception:
                            pass
                bm25 = StandardBM25(corpus_texts)
                bm_q = (bm25_query or query)
                bm_scores = bm25.score(bm_q)
                # Vector results mapped to chunk IDs
                vec_accum: Dict[str, float] = {}
                unmapped_texts: List[str] = []
                for h in vector_hits_rich:
                    t = (h.get('content') or '')
                    if not t:
                        continue
                    sig = t[:200].lower()
                    cid = sig_to_id.get(sig)
                    if cid:
                        vec_accum[cid] = max(vec_accum.get(cid, 0.0), float(h.get('score') or 0.0))
                    else:
                        unmapped_texts.append(t)
                # Use unified text-level fusion
                bm25_texts = [id_to_content.get(idx_to_id[i], '') for i, _ in enumerate(bm_scores) if 0 <= i < len(idx_to_id) and id_to_content.get(idx_to_id[i])]
                ordered = self._fuse_candidates(bm25_texts, vector_hits_rich, query)
                cap = getattr(retrieval, 'rerank_input_cap', 30)
                ordered = ordered[:cap]
                if len(ordered) < cap and unmapped_texts:
                    for t in unmapped_texts:
                        if len(ordered) >= cap:
                            break
                        sig = t[:200].lower()
                        if any(sig == s[:200].lower() for s in ordered):
                            continue
                        ordered.append(t)
                contexts = ordered
                content_to_row = content_to_row_local
            except Exception:
                contexts = []

        if not contexts:
            contexts = preselected_contexts if preselected_contexts is not None else self.retriever.retrieve(query, top_k=retrieval.hybrid_top_k)
            try:
                emb_avg = emb_avg if emb_avg is not None else self._embed_queries_avg(query)
                vector_hits_rich = self._qdrant_contexts_rich(query, tenant_id=tenant_id, top_k=retrieval.vector_top_k, emb_override=emb_avg)
            except Exception:
                vector_hits_rich = []
            try:
                field_value_hits_rich = self._qdrant_field_values_rich(query, tenant_id=tenant_id, top_k=getattr(retrieval, 'field_value_top_k', 8), emb_override=emb_avg)
            except Exception:
                field_value_hits_rich = []

        # Stitch adjacent chunks for vector results
        if vector_hits_rich:
            for hit in vector_hits_rich:
                text = hit.get("content") or ""
                doc_id = hit.get("document_id")
                idx = hit.get("chunk_index")
                if isinstance(doc_id, str) and isinstance(idx, int):
                    try:
                        neighbors = qdrant_service.get_adjacent_chunks(tenant_id, doc_id, start_index=idx, window=2)
                    except Exception:
                        neighbors = []
                    all_parts = []
                    prev_parts = [n.get("content", "") for n in neighbors if isinstance(n.get("chunk_index"), int) and n.get("chunk_index") < idx]
                    prev_parts.sort()
                    next_parts = [n.get("content", "") for n in neighbors if isinstance(n.get("chunk_index"), int) and n.get("chunk_index") > idx]
                    next_parts.sort()
                    all_parts.extend(prev_parts[-2:])
                    all_parts.append(text)
                    all_parts.extend(next_parts[:2])
                    stitched = "\n".join([p for p in all_parts if isinstance(p, str) and p])
                    if stitched:
                        stitched_texts.append(stitched)

        # Entity consolidation on contexts using vector metadata
        try:
            def _entity_key_from_meta(meta: Dict[str, Any]) -> str:
                if not isinstance(meta, dict):
                    return ""
                row = meta.get('row') if isinstance(meta.get('row'), dict) else None
                if not row:
                    return ""
                candidates = [
                    'employee_name', 'name', 'full_name', 'employee', 'person',
                    'first_name', 'last_name'
                ]
                row_norm = {str(k).strip().lower().replace(' ', '_'): str(v).strip() for k, v in row.items() if str(v).strip()}
                for ck in candidates:
                    if ck in row_norm and row_norm[ck]:
                        return row_norm[ck].lower()
                vals = list(row_norm.values())
                if vals:
                    return (vals[0] + (" " + vals[1] if len(vals) > 1 else "")).lower()
                return ""

            entity_to_contexts: Dict[str, List[str]] = {}
            if vector_hits_rich:
                for h in vector_hits_rich:
                    txt = (h.get('content') or '').strip()
                    meta = h.get('meta') or {}
                    ek = _entity_key_from_meta(meta)
                    if ek and txt:
                        entity_to_contexts.setdefault(ek, []).append(txt)
            if entity_to_contexts:
                consolidated: List[str] = []
                used = set()
                for ek, clist in entity_to_contexts.items():
                    if len(clist) > 1:
                        seen_local = set()
                        merged_parts = []
                        for c in clist:
                            if c.lower() in seen_local:
                                continue
                            seen_local.add(c.lower())
                            merged_parts.append(c)
                            used.add(c)
                        consolidated.append("\n".join(merged_parts))
                for c in contexts:
                    if (c or '').strip() and c not in used:
                        consolidated.append(c)
                contexts = consolidated
        except Exception:
            pass

        return contexts, vector_hits_rich, emb_avg, content_to_row, stitched_texts, field_value_hits_rich

    def _fuse_contexts(
        self,
        contexts: List[str],
        stitched_texts: List[str],
        vector_hits_rich: List[Dict[str, Any]],
        query: str,
        field_value_hits_rich: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        if not getattr(retrieval, 'hybrid_enabled', True):
            if stitched_texts or vector_hits_rich:
                combined = contexts + stitched_texts + [h.get('content', '') for h in (vector_hits_rich or []) if isinstance(h.get('content'), str)]
                seen = set(); dedup: List[str] = []
                for c in combined:
                    k = c[:200].lower()
                    if k in seen:
                        continue
                    seen.add(k)
                    dedup.append(c)
                return dedup[:20]
            return contexts

        fv_texts = [h.get('content', '') for h in (field_value_hits_rich or []) if isinstance(h.get('content'), str)]
        candidates = contexts + stitched_texts + [h.get('content', '') for h in (vector_hits_rich or []) if isinstance(h.get('content'), str)] + fv_texts
        bm25_texts = candidates[:]  # we will fuse at text level uniformly
        # Inject field_values into vector list with optional weight by repeating entries
        vf = field_value_hits_rich or []
        vector_all = list(vector_hits_rich or [])
        ordered = self._fuse_candidates(bm25_texts, vector_all, query, field_value_hits_rich=field_value_hits_rich)
        # Dedup and cap
        seen = set(); out: List[str] = []
        cap = getattr(retrieval, 'rerank_input_cap', 30)
        for t in ordered:
            k = t[:200].lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(t)
            if len(out) >= cap:
                break
        return out

    def _apply_advanced_reranking(
        self,
        contexts: List[str],
        vector_hits_rich: List[Dict[str, Any]],
        content_to_row: Dict[str, Dict[str, str]],
        query: str,
        activated_schema_fields: Optional[List[str]] = None,
    ) -> Tuple[List[str], Optional[Dict[str, Any]]]:
        reranking_info: Optional[Dict[str, Any]] = None
        if self.reranker_enabled and contexts and len(contexts) > 3:
            RERANK_REQUESTS.inc()
            start_time = time.time()
            try:
                logger.info(f"Applying reranking to {len(contexts)} contexts")
                bi_encoder_scores = self._get_bi_encoder_scores(query, contexts, vector_hits_rich)
                structured_contexts: List[str] = []
                label_map: Dict[str, str] = {}
                for h in (vector_hits_rich or []):
                    txt = (h.get('content') or '').strip()
                    meta = h.get('meta') or {}
                    row_map = meta.get('row') if isinstance(meta, dict) else None
                    if txt and isinstance(row_map, dict) and row_map:
                        label_map[txt] = self._format_labeled_row(row_map)
                try:
                    for txt, row_map in (content_to_row.items() if content_to_row else []):
                        if txt and txt not in label_map and isinstance(row_map, dict) and row_map:
                            label_map[txt] = self._format_labeled_row(row_map)
                except Exception:
                    pass
                for c in contexts:
                    structured_contexts.append(label_map.get(c, c))

                rerank_result = self.reranker.multi_stage_reranking(
                    query=query,
                    documents=structured_contexts,
                    bi_encoder_scores=bi_encoder_scores,
                    top_k=min(retrieval.rerank_top_k, len(structured_contexts))
                )
                # Schema-match bias: boost scores when fields match activated schema
                try:
                    bias_fields = set([str(f).strip().lower().replace(' ', '_') for f in (activated_schema_fields or []) if isinstance(f, str)])
                    if bias_fields and hasattr(rerank_result, 'scores') and rerank_result.scores:
                        factor = getattr(reranker_config, 'schema_bias_factor', 1.1)
                        # Map structured doc back to original
                        back_map: Dict[str, str] = {v: k for k, v in label_map.items()} if label_map else {}
                        for i in range(min(len(rerank_result.documents), len(rerank_result.scores))):
                            doc_struct = rerank_result.documents[i]
                            original = back_map.get(doc_struct, doc_struct)
                            matched = False
                            # Check vector hit meta rows for field keys
                            for h in (vector_hits_rich or []):
                                txt = (h.get('content') or '').strip()
                                if not txt or txt != original:
                                    continue
                                meta_h = h.get('meta') or {}
                                row_h = meta_h.get('row') if isinstance(meta_h, dict) else None
                                if isinstance(row_h, dict):
                                    row_keys = {str(k).strip().lower().replace(' ', '_') for k in row_h.keys()}
                                    if row_keys & bias_fields:
                                        matched = True
                                        break
                            if not matched:
                                # Parse field from field_value style content
                                m = re.match(r"^Field:\s*([^|]+)\|", original)
                                if m:
                                    fdisp = m.group(1).strip().lower().replace(' ', '_')
                                    if fdisp in bias_fields:
                                        matched = True
                            if matched:
                                try:
                                    rerank_result.scores[i] = float(rerank_result.scores[i]) * float(factor)
                                except Exception:
                                    pass
                        # Re-sort by adjusted scores
                        paired = list(zip(rerank_result.documents, rerank_result.scores))
                        paired.sort(key=lambda x: x[1], reverse=True)
                        rerank_result.documents = [d for d, _s in paired]
                        rerank_result.scores = [s for _d, s in paired]
                except Exception:
                    pass
                if label_map:
                    back_map: Dict[str, str] = {v: k for k, v in label_map.items()}
                    contexts = [back_map.get(d, d) for d in rerank_result.documents]
                else:
                    contexts = rerank_result.documents
                processing_time = time.time() - start_time
                RERANK_LATENCY.observe(processing_time)
                reranking_info = {
                    "method": rerank_result.method_used,
                    "processing_time": processing_time,
                    "original_count": len(contexts),
                    "reranked_count": len(rerank_result.documents)
                }
                logger.info(f"Reranking completed: method={rerank_result.method_used}, time={processing_time:.3f}s")
            except Exception as e:
                RERANK_ERRORS.inc()
                logger.error(f"Reranking failed: {e}")
                reranking_info = {"error": str(e), "fallback": True}
        return contexts, reranking_info

    def _llm_rerank_contexts(self, contexts: List[str], query: str) -> List[str]:
        if not contexts:
            return contexts
        try:
            return self.rerank_contexts_via_llm(
                query,
                contexts,
                top_k=getattr(retrieval, 'rerank_top_k', 10),
            )
        except Exception:
            return contexts

    def _classify_intent(self, query: str) -> str:
        """Lightweight intent classification for answer routing.
        Returns one of: 'yes_no', 'temporal', 'causal', 'descriptive'.
        """
        q = (query or "").strip().lower()
        # Temporal cues
        temporal_cues = ["when", "what date", "date of", "birth date", "hired", "joined", "start date", "dob", "birthday"]
        if any(c in q for c in temporal_cues):
            return "temporal"
        # Causal cues
        if q.startswith("why ") or " why " in q or " reason" in q or " because " in q or " due to " in q:
            return "causal"
        # Yes/No cues
        yesno_starts = ("is ", "are ", "was ", "were ", "does ", "do ", "did ", "has ", "have ", "can ", "could ", "should ")
        if q.startswith(yesno_starts):
            return "yes_no"
        # Descriptive default
        return "descriptive"

    def _normalize_text(self, text: str) -> str:
        """Lightweight normalization: lowercase, strip punctuation, collapse spaces, synonym canonicalization."""
        try:
            import re
            t = (text or "").lower()
            # Replace punctuation with spaces
            t = re.sub(r"[\p{P}\p{S}]", " ", t)
        except Exception:
            # Fallback regex class for punctuation if \p classes unsupported
            import re
            t = (text or "").lower()
            t = re.sub(r"[^a-z0-9\s]", " ", t)
        # Collapse whitespace
        t = " ".join(t.split())
        # Canonicalize common domain variants
        synonyms = {
            "dob": {"birthdate", "date_of_birth", "birthday"},
            "salary": {"pay", "compensation", "wage", "base_salary", "base pay"},
            "manager": {"supervisor", "boss", "reporting manager"},
            "department": {"dept", "division", "team", "unit"},
            "married": {"marital", "marriage"},
        }
        tokens = t.split()
        for i, tok in enumerate(tokens):
            for canon, alts in synonyms.items():
                if tok in alts:
                    tokens[i] = canon
        return " ".join(tokens)

    def _format_labeled_row(self, row_map: Dict[str, Any]) -> str:
        parts: List[str] = []
        for k, v in row_map.items():
            try:
                ks = str(k).strip()
                vs = str(v).strip()
            except Exception:
                continue
            if not ks or not vs:
                continue
            parts.append(f"{ks}: {vs}")
        return " | ".join(parts) if parts else ""

    

    def rerank_contexts_via_llm(self, query: str, contexts: List[str], top_k: int = 10) -> List[str]:
        """Ask LLM to score context snippets by relevance and return top_k. Best-effort."""
        if not self.openai_client or not contexts:
            return contexts[:top_k]
        try:
            # Build a compact list with indices for scoring
            limited = contexts[: min(30, len(contexts))]
            formatted = "\n\n".join([f"[{i}] {c[:600]}" for i, c in enumerate(limited)])
            prompt = (
                "Score the following CONTEXT snippets by relevance to the QUESTION from 0.0 to 1.0.\n"
                "Return ONLY a JSON array of the top indices in descending order of score.\n\n"
                f"QUESTION: {query}\n\nCONTEXT:\n{formatted}"
            )
            completion = self.openai_client.chat.completions.create(
                model=os.getenv("RAG_RERANK_MODEL", self.chat_model),
                temperature=0,
                messages=[
                    {"role": "system", "content": "You are a relevance scorer that outputs JSON arrays of indices only."},
                    {"role": "user", "content": prompt},
                ],
            )
            import json as _json
            text = (completion.choices[0].message.content or "[]").strip()
            indices = _json.loads(text)
            if isinstance(indices, list):
                ranked = []
                for idx in indices:
                    if isinstance(idx, int) and 0 <= idx < len(limited):
                        ranked.append(limited[idx])
                # Fill if fewer than requested
                for c in limited:
                    if c not in ranked:
                        ranked.append(c)
                return ranked[:top_k]
        except Exception:
            pass
        return contexts[:top_k]

    # Generic SQL aggregation over structured rows stored in KnowledgeChunk.meta.row
    def _aggregate_over_rows(
        self,
        db: Session,
        tenant_id: str,
        op: str,
        field: str,
        sheet: Optional[str] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        group_by: Optional[List[str]] = None,
        date_field: Optional[str] = None,
        time_range: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        def _norm(s: str) -> str:
            return s.strip().lower().replace(' ', '_')

        target = _norm(field)
        # Simple synonym map; can be extended
        synonyms: Dict[str, List[str]] = {
            'sales_amount': ['salesamount', 'sales_amount', 'amount', 'revenue', 'sales'],
        }

        # Gather candidate rows for this tenant (optionally filter by sheet via document title)
        q = (
            db.query(KnowledgeChunk, Document)
            .join(Document, KnowledgeChunk.document_id == Document.id)
            .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .filter(KnowledgeBase.tenant_id == tenant_id)
        )
        if isinstance(sheet, str) and sheet.strip():
            q = q.filter(Document.title.ilike(f"%{sheet.strip()}%"))
        pairs = q.all()
        if not pairs:
            return None

        # Discover available columns to resolve target field and collect samples for type inference
        available_cols: set[str] = set()
        col_samples: Dict[str, List[str]] = {}
        for kc, _doc in pairs:
            meta = kc.meta or {}
            row_map = meta.get('row') if isinstance(meta, dict) else None
            if isinstance(row_map, dict):
                for k in row_map.keys():
                    nk = _norm(str(k))
                    available_cols.add(nk)
                    v = row_map.get(k)
                    if isinstance(v, str):
                        col_samples.setdefault(nk, []).append(v)
                        if len(col_samples[nk]) > 50:
                            col_samples[nk] = col_samples[nk][:50]

        def _looks_date(val: str) -> bool:
            s = str(val).strip()
            if not s:
                return False
            # ISO-like date prefix check YYYY-MM-DD
            if len(s) >= 10 and s[0:4].isdigit() and s[4] in {'-','/'} and s[5:7].isdigit() and s[7] in {'-','/'} and s[8:10].isdigit():
                return True
            # Year-only
            if len(s) == 4 and s.isdigit():
                return True
            return False

        def _clean_numeric(val: str) -> Optional[float]:
            try:
                s = str(val).strip()
                if not s:
                    return None
                neg = False
                if s.startswith('(') and s.endswith(')'):
                    neg = True
                    s = s[1:-1]
                s = s.replace('%','')
                for ch in ['$', '€', '£', '¥', 'RM']:
                    s = s.replace(ch, '')
                s = s.replace(',', '').replace(' ', '')
                if s in {'', '.', '-', '+', 'NaN', 'nan'}:
                    return None
                num = float(s)
                return -num if neg else num
            except Exception:
                return None

        # Infer column types
        col_types: Dict[str, str] = {}
        for col, samples in col_samples.items():
            n_numeric = 0
            n_date = 0
            n_total = 0
            for v in samples[:30]:
                n_total += 1
                if _clean_numeric(v) is not None:
                    n_numeric += 1
                if _looks_date(v):
                    n_date += 1
            if n_total == 0:
                continue
            if n_numeric / n_total >= 0.6:
                col_types[col] = 'numeric'
            elif n_date / n_total >= 0.6:
                col_types[col] = 'date'
            else:
                col_types[col] = 'text'

        resolved = None
        if target in available_cols:
            resolved = target
        else:
            for _base, syns in synonyms.items():
                if target == _base or target in syns:
                    for s in syns:
                        if s in available_cols:
                            resolved = s
                            break
                if resolved:
                    break
        if not resolved:
            for c in available_cols:
                if target and target in c:
                    resolved = c
                    break
        if not resolved and target:
            # Fuzzy match using difflib
            candidates = difflib.get_close_matches(target, list(available_cols), n=1, cutoff=0.7)
            if candidates:
                resolved = candidates[0]
        if not resolved:
            return None

        flist = filters or []
        gby = [ _norm(g) for g in (group_by or []) if isinstance(g, str) and g.strip() ]
        resolved_date = _norm(date_field) if isinstance(date_field, str) and date_field.strip() else None
        if time_range and not resolved_date:
            # infer a likely date column
            date_like = [c for c,t in col_types.items() if t == 'date']
            prefer = [c for c in date_like if 'date' in c or 'order' in c or 'time' in c or 'year' in c]
            if prefer:
                resolved_date = prefer[0]
            elif date_like:
                resolved_date = date_like[0]

        def _in_timerange(cell: str) -> bool:
            if not time_range or not resolved_date:
                return True
            try:
                # Try to parse date (YYYY-MM-DD or YYYY/MM/DD). Fallback to prefix year compare
                cell_s = str(cell).strip()
                if time_range.get('type') == 'year':
                    y = str(time_range.get('value') or '')
                    return cell_s.startswith(y)
                if time_range.get('type') == 'between':
                    start = str(time_range.get('start') or '')
                    end = str(time_range.get('end') or '')
                    return (start <= cell_s <= end)
                if time_range.get('type') == 'quarter':
                    # crude quarter check by month; expects like 'Q1 2014'
                    v = str(time_range.get('value') or '')
                    m = v.upper().split()
                    if len(m) == 2 and m[0] in {'Q1','Q2','Q3','Q4'}:
                        year = m[1]
                        if not cell_s.startswith(year):
                            return False
                        month = int(cell_s[5:7]) if len(cell_s) >= 7 and cell_s[5:7].isdigit() else None
                        if month is None:
                            return False
                        if m[0] == 'Q1':
                            return 1 <= month <= 3
                        if m[0] == 'Q2':
                            return 4 <= month <= 6
                        if m[0] == 'Q3':
                            return 7 <= month <= 9
                        if m[0] == 'Q4':
                            return 10 <= month <= 12
                return True
            except Exception:
                return True

        # Aggregation state
        grouped_nums: Dict[tuple, List[float]] = {}
        values: List[float] = []
        grouped_distinct: Dict[tuple, set] = {}
        distinct_all: set = set()
        for kc, _doc in pairs:
            meta = kc.meta or {}
            row_map = meta.get('row') if isinstance(meta, dict) else None
            if not isinstance(row_map, dict):
                continue
            ok = True
            for f in flist:
                try:
                    col = _norm(str(f.get('column')))
                    val = str(f.get('value') or '')
                    opx = str(f.get('op') or 'eq').lower()
                    if not col or val is None:
                        continue
                    cell = str(row_map.get(col, ''))
                    if opx in {'eq','='} and cell.lower() != val.lower(): ok = False; break
                    if opx in {'ne','!='} and cell.lower() == val.lower(): ok = False; break
                    if opx in {'contains'} and val.lower() not in cell.lower(): ok = False; break
                    if opx in {'gt','gte','lt','lte'}:
                        try:
                            cnum = float(cell.replace(',','').replace('$','').strip())
                            vnum = float(val.replace(',','').replace('$','').strip())
                            if opx == 'gt' and not (cnum > vnum): ok = False; break
                            if opx == 'gte' and not (cnum >= vnum): ok = False; break
                            if opx == 'lt' and not (cnum < vnum): ok = False; break
                            if opx == 'lte' and not (cnum <= vnum): ok = False; break
                        except Exception:
                            continue
                except Exception:
                    continue
            if not ok:
                continue
            # time range filter on date_field
            if resolved_date:
                if not _in_timerange(str(row_map.get(resolved_date, ''))):
                    continue
            raw = row_map.get(resolved)
            if opn == 'distinct_count':
                raw_str = str(raw) if raw is not None else ''
                if gby:
                    key = tuple(str(row_map.get(g, '')).strip() for g in gby)
                    grouped_distinct.setdefault(key, set()).add(raw_str)
                else:
                    distinct_all.add(raw_str)
                continue
            if not isinstance(raw, str) or not raw.strip():
                continue
            num = _clean_numeric(raw)
            if num is None:
                continue
            if gby:
                key = tuple(str(row_map.get(g, '')).strip() for g in gby)
                grouped_nums.setdefault(key, []).append(num)
            else:
                values.append(num)

        opn = (op or '').strip().lower()
        def _agg(nums: List[float]) -> float:
            if not nums:
                return 0.0
            if opn == 'sum':
                return float(sum(nums))
            if opn == 'avg':
                return float(sum(nums) / max(1, len(nums)))
            if opn == 'min':
                return float(min(nums))
            if opn == 'max':
                return float(max(nums))
            if opn in {'count'}:
                return float(len(nums))
            return float(sum(nums))

        if gby:
            if opn == 'distinct_count':
                if not grouped_distinct:
                    return None
                parts = []
                for key, s in grouped_distinct.items():
                    label = ", ".join([str(k) if k is not None else '' for k in key])
                    parts.append(f"{label}: {float(len(s)):,.2f}")
                return "\n".join(sorted(parts))
            if not grouped_nums:
                return None
            parts = []
            for key, nums in grouped_nums.items():
                label = ", ".join([str(k) if k is not None else '' for k in key])
                parts.append(f"{label}: {_agg(nums):,.2f}")
            return "\n".join(sorted(parts))
        else:
            if opn == 'distinct_count':
                return f"{float(len(distinct_all)):,.2f}"
            total = _agg(values)
            return f"{total:,.2f}"

    def _embed_query(self, text: str) -> Optional[list[float]]:
        """Embed query with OpenAI if available for Qdrant search."""
        if not self.openai_client:
            return None
        try:
            model = self._select_openai_embed_model()
            resp = self.openai_client.embeddings.create(
                model=model,
                input=[text],
            )
            return resp.data[0].embedding
        except Exception:
            return None

    def _embed_with_cache(self, text: str) -> Optional[list[float]]:
        model = self._select_openai_embed_model()
        key = f"emb:{model}:{hash(text)}"
        cached = redis_cache.get_tenant_key("global", key)
        if isinstance(cached, list):
            return cached
        emb = self._embed_query(text)
        if emb:
            redis_cache.set_tenant_key("global", key, emb, ttl=3600)
        return emb

    def _select_openai_embed_model(self) -> str:
        """Return a valid OpenAI embedding model ID, never a HF ID.

        Falls back to text-embedding-3-small (1536-d) to match current Qdrant dim.
        """
        candidate = os.getenv("OPENAI_EMBED_MODEL") or os.getenv("RAG_EMBED_MODEL") or getattr(retrieval, 'embedding_model', 'text-embedding-3-small')
        # Heuristic: HF model IDs contain '/'
        if "/" in str(candidate):
            return "text-embedding-3-small"
        # Guard against chat models being set here
        if str(candidate).startswith("gpt-"):
            return "text-embedding-3-small"
        return str(candidate or "text-embedding-3-small")

    def _embed_queries_avg(self, base_query: str, max_variants: int = 3) -> Optional[list[float]]:
        queries = [base_query]
        if getattr(retrieval, 'expansion_enabled', True):
            try:
                # Schema-aware expansion: include known schema fields
                tenant = getattr(self, 'current_tenant_id', 'global') or 'global'
                schema_fields = self._get_schema_fields_for_tenant(tenant)
                variants = self.expand_queries(base_query, schema_fields=schema_fields)[:max_variants]
                queries.extend(variants)
            except Exception:
                pass
        # Normalize before embedding
        embs: List[List[float]] = []
        for q in queries:
            qn = self._normalize_text(q)
            e = self._embed_with_cache(qn)
            if e:
                embs.append(e)
        if not embs:
            return None
        dim = len(embs[0])
        avg = [0.0] * dim
        for v in embs:
            if len(v) != dim:
                continue
            for i in range(dim):
                avg[i] += v[i]
        n = max(1, len(embs))
        for i in range(dim):
            avg[i] /= n
        return avg

    def _get_schema_fields_for_tenant(self, tenant_id: str) -> List[str]:
        # 1) Redis cache
        try:
            cached = redis_cache.get_tenant_key(tenant_id, "schema:fields")
            if isinstance(cached, list) and cached:
                return [str(x) for x in cached if isinstance(x, (str,))]
        except Exception:
            pass
        fields: List[str] = []
        # 2) Qdrant schema collection as fallback
        try:
            items = qdrant_service.list_schema_fields(tenant_id, limit=2000)
            for it in items:
                pl = it.get('payload') or {}
                nm = pl.get('field_name')
                if isinstance(nm, str) and nm and nm not in fields:
                    fields.append(nm)
        except Exception:
            pass
        # 3) Persist to Redis for next time
        try:
            if fields:
                redis_cache.set_tenant_key(tenant_id, "schema:fields", fields, ttl=24*3600)
        except Exception:
            pass
        return fields

    def expand_queries(self, base_query: str, schema_fields: Optional[List[str]] = None, tenant_id: Optional[str] = None) -> List[str]:
        """Generate paraphrases/expansions using LLM with schema awareness with caching.

        Returns up to 3-5 short alternative queries that include relevant field names.
        """
        # Cache check
        try:
            t = tenant_id or getattr(self, 'current_tenant_id', 'global') or 'global'
            cache_key = f"expand:{t}:{hash(base_query)}"
            cached = redis_cache.get_tenant_key(t, cache_key)
            if isinstance(cached, list) and cached:
                return [str(x) for x in cached][:5]
        except Exception:
            pass

        expansions: List[str] = []
        # Merge provided fields with nearest schema fields from Qdrant
        try:
            t = tenant_id or getattr(self, 'current_tenant_id', 'global') or 'global'
            nearest = self._nearest_schema_fields(base_query, t, top_k=8)
        except Exception:
            nearest = []
        merged_fields = []
        for f in (schema_fields or []) + nearest:
            if isinstance(f, str) and f and f not in merged_fields:
                merged_fields.append(f)
        fields_snippet = ", ".join(merged_fields[:20]) if merged_fields else ""
        prompt = (
            "Given the user query, generate 3 alternative phrasings using any applicable field names "
            "from this schema list (if relevant). Return one per line, concise.\n\n"
            f"Schema fields: {fields_snippet}\n\n"
            f"Query: {base_query}"
        )
        if self.openai_client:
            try:
                completion = self.openai_client.chat.completions.create(
                    model=self.chat_model,
                    temperature=0.2,
                    messages=[
                        {"role": "system", "content": "You produce short alternate queries, one per line."},
                        {"role": "user", "content": prompt},
                    ],
                )
                raw = (completion.choices[0].message.content or "").strip()
                for line in raw.splitlines():
                    s = line.strip(" -\t\n")
                    if s and s.lower() != base_query.lower():
                        expansions.append(s)
            except Exception:
                pass
        # Fallback heuristic expansions
        if not expansions and merged_fields:
            for f in merged_fields[:3]:
                expansions.append(f"{base_query} {f}")
        expansions = expansions[:5]
        # Cache set
        try:
            ttl = getattr(retrieval, 'expand_cache_ttl', 1800)
            redis_cache.set_tenant_key(t, cache_key, expansions, ttl=ttl)
        except Exception:
            pass
        return expansions

    def _expand_with_schema(self, query: str, tenant_id: str) -> Dict[str, Any]:
        """Schema-aware query expansion: combine nearest schema fields + LLM paraphrases.

        Returns: {"expanded_terms": List[str], "variants": List[str]}
        """
        expanded_terms: List[str] = []
        # nearest schema fields
        try:
            nearest = self._nearest_schema_fields(query, tenant_id, top_k=8)
            # Normalize scores via softmax-like scaling from raw distances if available
            scored: List[Tuple[str, float]] = []
            if nearest:
                # Re-query with raw results to get scores
                emb = self._embed_with_cache(query)
                raw = qdrant_service.search_schema_fields(query_embedding=emb, tenant_id=tenant_id, top_k=8)
                for r in raw:
                    nm = (r.get('payload') or {}).get('field_name')
                    sc = float(r.get('score') or 0.0)
                    if isinstance(nm, str) and nm:
                        scored.append((nm, sc))
            if scored:
                # softmax over scores
                import math as _m
                maxs = max(s for (_n, s) in scored) if scored else 1.0
                exps = [ _m.exp((s - maxs)) for (_n, s) in scored ]
                ssum = sum(exps) or 1.0
                weights = {n: (e/ssum) for (e, (n, _s)) in zip(exps, scored)}
                # keep top with threshold
                for n, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
                    if w < 0.05:
                        continue
                    if n not in expanded_terms:
                        expanded_terms.append(n)
            else:
                for f in nearest:
                    if isinstance(f, str) and f and f not in expanded_terms:
                        expanded_terms.append(f)
        except Exception:
            nearest = []
        # LLM/heuristic variants
        try:
            variants = self.expand_queries(query, schema_fields=expanded_terms, tenant_id=tenant_id)
        except Exception:
            variants = []
        # Log activated schema fields for synonym retraining
        try:
            if expanded_terms:
                from shared.cache.synonyms_store import SynonymsStore
                # store canonical self-mappings as activity signals
                SynonymsStore.put_many(tenant_id, {t: t for t in expanded_terms})
        except Exception:
            pass
        return {"expanded_terms": expanded_terms, "variants": variants}

    def _nearest_schema_fields(self, query: str, tenant_id: str, top_k: int = 8) -> List[str]:
        emb = self._embed_with_cache(query)
        if not emb:
            return []
        try:
            results = qdrant_service.search_schema_fields(query_embedding=emb, tenant_id=tenant_id, top_k=top_k)
        except Exception:
            return []
        fields: List[str] = []
        for r in results:
            payload = r.get('payload') or {}
            name = payload.get('field_name')
            if isinstance(name, str) and name and name not in fields:
                fields.append(name)
        return fields

    def _qdrant_contexts(self, query: str, tenant_id: str, top_k: int = 6, emb_override: Optional[list[float]] = None) -> list[str]:
        emb = emb_override if emb_override is not None else self._embed_query(query)
        if not emb:
            return []
        try:
            results = qdrant_service.search_similar_chunks(query_embedding=emb, tenant_id=tenant_id, top_k=top_k)
            out: list[str] = []
            for r in results:
                payload = r.get("payload") or {}
                content = payload.get("content")
                if isinstance(content, str) and content:
                    out.append(content)
            return out
        except Exception:
            return []

    def _qdrant_contexts_rich(self, query: str, tenant_id: str, top_k: int = 6, emb_override: Optional[list[float]] = None) -> List[Dict[str, Any]]:
        emb = emb_override if emb_override is not None else self._embed_query(query)
        if not emb:
            return []
        try:
            results = qdrant_service.search_similar_chunks(query_embedding=emb, tenant_id=tenant_id, top_k=top_k)
            rich: List[Dict[str, Any]] = []
            for r in results:
                payload = r.get("payload") or {}
                content = payload.get("content")
                if isinstance(content, str) and content:
                    rich.append({
                        "content": content,
                        "document_id": payload.get("document_id"),
                        "document_title": payload.get("document_title"),
                        "chunk_index": payload.get("chunk_index"),
                        "chapter_num": payload.get("chapter_num"),
                        "chapter_title": payload.get("chapter_title"),
                        "page": payload.get("page"),
                        "score": r.get("score"),
                        "meta": payload.get("metadata", {}),
                    })
            return rich
        except Exception:
            return []

    def _qdrant_field_values_rich(self, query: str, tenant_id: str, top_k: int = 8, emb_override: Optional[list[float]] = None) -> List[Dict[str, Any]]:
        emb = emb_override if emb_override is not None else self._embed_query(query)
        if not emb:
            return []
        try:
            results = qdrant_service.search_field_values(query_embedding=emb, tenant_id=tenant_id, top_k=top_k)
            rich: List[Dict[str, Any]] = []
            for r in results:
                payload = r.get("payload") or {}
                text = payload.get("content") or ""
                if not isinstance(text, str) or not text:
                    fd = payload.get("field_display") or payload.get("field_name") or ""
                    vr = payload.get("value_raw") or payload.get("value_norm") or ""
                    ridx = payload.get("row_index")
                    sheet = payload.get("sheet") or ""
                    title = payload.get("source_file") or ""
                    parts = [
                        f"Field: {fd}" if fd else None,
                        f"Value: {vr}" if vr else None,
                        f"Record: {int(ridx)+1}" if isinstance(ridx, int) else None,
                        f"Sheet: {sheet}" if sheet else None,
                        f"File: {title}" if title else None,
                    ]
                    text = " | ".join([p for p in parts if p])
                rich.append({
                    "content": text,
                    "field_name": payload.get("field_name"),
                    "field_display": payload.get("field_display"),
                    "value_raw": payload.get("value_raw"),
                    "value_norm": payload.get("value_norm"),
                    "document_id": payload.get("document_id"),
                    "row_index": payload.get("row_index"),
                    "score": r.get("score"),
                    "meta": payload,
                })
            return rich
        except Exception:
            return []

    # Public web fallback via Wikipedia API (no API key required)
    def _public_web_fallback(self, query: str) -> Optional[Dict[str, Any]]:
        try:
            q = query.strip()
            if not q:
                return None
            # Step 1: use MediaWiki opensearch to find best title
            params = {
                "action": "opensearch",
                "search": q,
                "limit": 1,
                "namespace": 0,
                "format": "json",
            }
            url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
            with urllib.request.urlopen(url, timeout=6) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(raw)
            if not isinstance(data, list) or len(data) < 4:
                return None
            titles = data[1] if isinstance(data[1], list) else []
            links = data[3] if isinstance(data[3], list) else []
            if not titles:
                return None
            title = titles[0]
            link = links[0] if links else f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"
            # Step 2: get summary
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
            with urllib.request.urlopen(summary_url, timeout=6) as resp2:
                raw2 = resp2.read().decode("utf-8", errors="ignore")
            sdata = json.loads(raw2)
            extract = sdata.get("extract") if isinstance(sdata, dict) else None
            if not isinstance(extract, str) or not extract.strip():
                return None
            response = extract.strip()
            citation = {
                "source": link,
                "title": f"Wikipedia • {title}",
                "relevance": 0.6,
                "snippet": response[:160],
            }
            response_with_notice = (
                response
                + "\n\nNote: This answer uses public web information (not your uploaded knowledge).\n"
                + f"Source: {link}"
            )
            return {"response": response_with_notice, "citations": [citation], "confidence": 0.5, "requiresHuman": False}
        except Exception:
            return None

    # Public LLM fallback (ChatGPT-style): generate an answer from general knowledge with sources
    def _public_llm_fallback(self, query: str) -> Optional[Dict[str, Any]]:
        if not self.openai_client:
            return None
        try:
            system = (
                "You answer using public knowledge only (no internal DB). Your name is Omni. "
                "Return STRICT JSON with keys: answer (string), sources (array of {title,url}). "
                "Prefer authoritative sources (official docs, standards, reputable orgs). "
                "Include 1-3 sources. If unsure of an exact URL, use the organization's homepage."
            )
            completion = self.openai_client.chat.completions.create(
                model=self.chat_model,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": query},
                ],
            )
            raw = (completion.choices[0].message.content or "").strip()
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            ans = data.get("answer")
            srcs = data.get("sources")
            if not isinstance(ans, str) or not ans.strip():
                return None
            citations: List[Dict[str, Any]] = []
            if isinstance(srcs, list):
                for s in srcs[:3]:
                    if not isinstance(s, dict):
                        continue
                    title = s.get("title")
                    url = s.get("url")
                    if isinstance(title, str) and title and isinstance(url, str) and url:
                        citations.append({
                            "source": url,
                            "title": title,
                            "relevance": 0.6,
                            "snippet": ans[:160],
                        })
            notice = (
                "\n\nNote: This answer is generated from public web knowledge (not your uploaded knowledge)."
            )
            return {"response": ans + notice, "citations": citations, "confidence": 0.6, "requiresHuman": False}
        except Exception:
            return None
        try:
            results = qdrant_service.search_similar_chunks(query_embedding=emb, tenant_id=tenant_id, top_k=top_k)
            rich: List[Dict[str, Any]] = []
            for r in results:
                payload = r.get("payload") or {}
                content = payload.get("content")
                if isinstance(content, str) and content:
                    rich.append({
                        "content": content,
                        "document_id": payload.get("document_id"),
                        "document_title": payload.get("document_title"),
                        "chunk_index": payload.get("chunk_index"),
                        "chapter_num": payload.get("chapter_num"),
                        "chapter_title": payload.get("chapter_title"),
                        "page": payload.get("page"),
                        "score": r.get("score"),
                    })
            return rich
        except Exception:
            return []

    def answer(self, query: str, preselected_contexts: Optional[List[str]] = None, tenant_id: str = "global", db: Optional[Session] = None) -> Dict[str, Any]:
        # Cache
        cache_key = f"rag:answer:{tenant_id}:{hash(query)}"
        cached = redis_cache.get_tenant_key(tenant_id, cache_key)
        if isinstance(cached, dict) and cached.get("response"):
            return cached

        # Set execution context for helpers
        try:
            self.current_tenant_id = tenant_id
            if db is not None:
                self.db = db
        except Exception:
            pass

        # Identity questions
        ql_id = (query or "").strip().lower()
        if any(p in ql_id for p in ["what is your name", "what's your name", "who are you", "your name", "what is ur name", "name please", "what are you called"]):
            result_id = {"response": "My name is Omni.", "citations": [], "confidence": 0.99, "requiresHuman": False}
            redis_cache.set_tenant_key(tenant_id, cache_key, result_id, ttl=self.cache_ttl_seconds)
            return result_id

        # Schema-aware expansion (terms + variants) prior to retrieval
        expansion_terms: List[str] = []
        if getattr(retrieval, 'expansion_enabled', True):
            try:
                exp = self._expand_with_schema(query, tenant_id)
                expansion_terms = exp.get('expanded_terms', []) or []
            except Exception:
                pass

        # Build enriched BM25 query with schema hints
        bm25_hint = " ".join([t for t in expansion_terms[:8]])
        bm25_query = (query + (" " + bm25_hint if bm25_hint else "")).strip()

        # Prepare candidates (retrieval + stitching + entity consolidation)
        contexts, vector_hits_rich, emb_avg, content_to_row, stitched_texts, field_value_hits_rich = self._prepare_candidates(
            query, preselected_contexts, tenant_id, db, bm25_query=bm25_query
        )

        # Fuse contexts
        contexts = self._fuse_contexts(contexts, stitched_texts, vector_hits_rich, query, field_value_hits_rich)

        # Advanced reranker (with schema bias)
        contexts, reranking_info = self._apply_advanced_reranking(
            contexts, vector_hits_rich, content_to_row, query, activated_schema_fields=expansion_terms
        )

        # LLM rerank (lightweight)
        contexts = self._llm_rerank_contexts(contexts, query)
        # If policy-like question, extract precise sentences as a shortcut answer
        ql = query.lower()
        def split_sentences(text: str) -> List[str]:
            parts = re.split(r"(?<=[\.!?])\s+|\n+|;\s+", text)
            return [p.strip() for p in parts if p and len(p.strip()) > 2]

        def score_sentence(sent: str, terms: List[str]) -> float:
            sl = sent.lower()
            hits = sum(1 for t in terms if t in sl)
            return hits + min(len(sent) / 200.0, 1.0)

        def extract_policy_answer(ctxs: List[str], terms: List[str]) -> List[str]:
            scored: List[tuple[float, str]] = []
            for c in ctxs:
                for s in split_sentences(c):
                    sc = score_sentence(s, terms)
                    if sc > 0:
                        scored.append((sc, s))
            scored.sort(key=lambda x: x[0], reverse=True)
            unique: List[str] = []
            seen = set()
            for _sc, s in scored:
                k = s.lower()
                if k in seen:
                    continue
                seen.add(k)
                unique.append(s)
                if len(unique) >= 5:
                    break
            return unique

        is_policy_query = any(t in ql for t in ["policy", "policies", "guideline", "rules"]) and any(t in ql for t in ["currency", "conversion", "unwithdrawn", "withdrawn"])
        if contexts and is_policy_query:
            terms = ["currency", "conversion", "unwithdrawn", "withdrawn", "loan", "amount", "approved currency", "variable spread", "minimum", "maximum"]
            top_sents = extract_policy_answer(contexts, terms)
            if top_sents:
                bullets = "\n- " + "\n- ".join(top_sents)
                response = f"Policy summary:\n{bullets}"
                citations = [
                    {"source": f"doc_{i}", "title": f"Document {i}", "relevance": 0.9 - i*0.1, "snippet": (contexts[i] if i < len(contexts) else "")[:160]}
                    for i in range(min(3, len(contexts)))
                ]
                result = {
                    "response": response,
                    "citations": citations,
                    "confidence": 0.85,
                    "requiresHuman": False,
                }
                redis_cache.set_tenant_key("global", cache_key, result, ttl=self.cache_ttl_seconds)
                if reranking_info:
                    result["reranking"] = reranking_info
                return result

        # AI-driven plan: let the model decide the strategy and what to look for
        plan = self.plan(query)

        # Tabular aggregation path (planner-driven, no hardcoded patterns)
        agg = plan.get('aggregation') if isinstance(plan, dict) else None
        if agg and isinstance(agg, dict):
            op = str(agg.get('op') or '')
            field = str(agg.get('field') or '')
            sheet = agg.get('sheet')
            filters = agg.get('filters') if isinstance(agg.get('filters'), list) else []
            # Prefer deterministic SQL aggregation over structured rows when DB session available
            if db is not None and op and field:
                try:
                    agg_val = self._aggregate_over_rows(
                        db=db,
                        tenant_id=tenant_id,
                        op=op,
                        field=field,
                        sheet=sheet,
                        filters=filters,
                        group_by=agg.get('group_by'),
                        date_field=agg.get('date_field'),
                        time_range=agg.get('time_range'),
                    )
                except Exception:
                    agg_val = None
                if isinstance(agg_val, str):
                    response_text = f"Result: {agg_val}"
                    res = {"response": response_text, "citations": [], "confidence": 0.95, "requiresHuman": False}
                    redis_cache.set_tenant_key(tenant_id, cache_key, res, ttl=self.cache_ttl_seconds)
                    return res
            # Build a focused context of tabular rows
            # Deterministic aggregation if we have rich hits and a DB session
            if 'vector_hits_rich' in locals() and vector_hits_rich and db is not None:
                import csv as _csv, io as _io
                # Map document_id -> header columns (lowercased) from Document.meta
                doc_ids = {h.get('document_id') for h in vector_hits_rich if isinstance(h.get('document_id'), str)}
                doc_columns: dict[str, list[str]] = {}
                for did in doc_ids:
                    if not isinstance(did, str):
                        continue
                    try:
                        d = db.get(DbDocument, did)
                        if d and isinstance(d.meta, dict) and isinstance(d.meta.get('columns'), list):
                            cols = [str(c).strip().lower() for c in d.meta.get('columns')]
                            doc_columns[did] = cols
                    except Exception:
                        continue
                # Normalize function
                def _norm(s: str) -> str:
                    return s.strip().lower().replace(' ', '_')
                target_field = _norm(field) if field else ''
                # Apply filters and aggregate
                values: list[float] = []
                for hit in vector_hits_rich:
                    row_text = hit.get('content') or ''
                    did = hit.get('document_id')
                    cols = doc_columns.get(did or '', [])
                    if not cols:
                        continue
                    try:
                        reader = _csv.reader(_io.StringIO(row_text))
                        row = next(reader)
                    except Exception:
                        continue
                    # Build row dict
                    row_map = {}
                    for i, col in enumerate(cols):
                        if i < len(row):
                            row_map[_norm(col)] = str(row[i])
                    # Filter check
                    ok = True
                    for f in filters:
                        try:
                            fc = _norm(str(f.get('column')))
                            fv = str(f.get('value') or '')
                            if fc and fc in row_map:
                                if fv and fv.lower() not in row_map[fc].lower():
                                    ok = False; break
                        except Exception:
                            continue
                    if not ok:
                        continue
                    # Extract numeric
                    val_raw = row_map.get(target_field, '')
                    if not isinstance(val_raw, str) or not val_raw:
                        continue
                    try:
                        num = float(val_raw.replace(',', '').replace('$', '').strip())
                        values.append(num)
                    except Exception:
                        continue
                if values:
                    result_num: float
                    if op == 'sum':
                        result_num = float(sum(values))
                    elif op == 'avg':
                        result_num = float(sum(values) / max(1, len(values)))
                    elif op == 'count':
                        result_num = float(len(values))
                    else:
                        result_num = float(sum(values))
                    response_text = f"Result: {result_num:,.2f}"
                    res = {"response": response_text, "citations": citations[:3] if 'citations' in locals() else [], "confidence": 0.9, "requiresHuman": False}
                    redis_cache.set_tenant_key(tenant_id, cache_key, res, ttl=self.cache_ttl_seconds)
                    return res
            # Fallback to LLM aggregation if deterministic path unavailable
            if self.openai_client and op and field:
                focused = contexts
                table_text = "\n".join(focused[:50])
                try:
                    completion_calc = self.openai_client.chat.completions.create(
                        model=self.chat_model,
                        temperature=0,
                        messages=[
                            {"role": "system", "content": "You are a precise data analyst. Parse rows and compute the requested aggregate exactly."},
                            {"role": "user", "content": f"OP={op}; FIELD={field}; FILTERS={filters}; SHEET={sheet or ''}\nROWS:\n{table_text}\n\nReturn only the result prefixed with 'Result: '"},
                        ],
                    )
                    out = (completion_calc.choices[0].message.content or '').strip()
                    if out:
                        res = {"response": out, "citations": citations[:3] if 'citations' in locals() else [], "confidence": 0.7, "requiresHuman": False}
                        redis_cache.set_tenant_key(tenant_id, cache_key, res, ttl=self.cache_ttl_seconds)
                        return res
                except Exception:
                    pass

        # Generic path: Use OpenAI chat generation augmented with plan
        # Rerank contexts via LLM if available for better grounding
        contexts = self.rerank_contexts_via_llm(query, contexts, top_k=retrieval.rerank_top_k)

        if not contexts:
            # Try LLM public knowledge fallback first
            pub_res = self._public_llm_fallback(query)
            if isinstance(pub_res, dict) and pub_res.get("response"):
                redis_cache.set_tenant_key(tenant_id, cache_key, pub_res, ttl=self.cache_ttl_seconds)
                return pub_res
            # Then try Wikipedia summary as a lightweight backup
            web_res = self._public_web_fallback(query)
            if isinstance(web_res, dict) and web_res.get("response"):
                redis_cache.set_tenant_key(tenant_id, cache_key, web_res, ttl=self.cache_ttl_seconds)
                return web_res
            result = {
                "response": "I don’t have that information in the current database.",
                "citations": [],
                "confidence": 0.0,
                "requiresHuman": True,
            }
            redis_cache.set_tenant_key(tenant_id, cache_key, result, ttl=self.cache_ttl_seconds)
            if reranking_info:
                result["reranking"] = reranking_info
            return result

        # If the user asks for chapter counts, try to compute from Qdrant payloads
        ql_simple = query.lower()
        if any(k in ql_simple for k in ["how many chapters", "number of chapters", "chapters are there"]):
            try:
                chapter_payloads = qdrant_service.list_chapters(tenant_id=tenant_id, limit=5000)
                nums = {int(p["chapter_num"]) for p in chapter_payloads if isinstance(p.get("chapter_num"), int)}
                titles = {p.get("chapter_title") for p in chapter_payloads if isinstance(p.get("chapter_title"), str) and p.get("chapter_title")}
                if nums or titles:
                    count = len(nums) if nums else len(titles)
                    response = f"There are at least {count} chapters indexed from the uploaded documents."
                    result = {"response": response, "citations": [], "confidence": 0.7, "requiresHuman": False}
                    redis_cache.set_tenant_key(tenant_id, cache_key, result, ttl=self.cache_ttl_seconds)
                    if reranking_info:
                        result["reranking"] = reranking_info
                    return result
            except Exception:
                pass
            # Fallback to SQL if vector store has no payloads
            if db is not None:
                try:
                    q = (
                        db.query(KnowledgeChunk)
                        .join(Document, KnowledgeChunk.document_id == Document.id)
                        .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
                        .filter(KnowledgeBase.tenant_id == tenant_id)
                    )
                    nums_sql = set()
                    titles_sql = set()
                    for kc in q:
                        meta = kc.meta or {}
                        if isinstance(meta, dict):
                            n = meta.get("chapter_num")
                            t = meta.get("chapter_title")
                            if isinstance(n, int):
                                nums_sql.add(n)
                            if isinstance(t, str) and t:
                                titles_sql.add(t)
                    if nums_sql or titles_sql:
                        count = len(nums_sql) if nums_sql else len(titles_sql)
                        response = f"There are at least {count} chapters indexed from the uploaded documents."
                        result = {"response": response, "citations": [], "confidence": 0.65, "requiresHuman": False}
                        redis_cache.set_tenant_key(tenant_id, cache_key, result, ttl=self.cache_ttl_seconds)
                        if reranking_info:
                            result["reranking"] = reranking_info
                        return result
                except Exception:
                    pass

        # Optional rule-based helpers (can be disabled via tuning)
        if retrieval.rules_enabled and ("chapter" in ql_simple) and ("title" in ql_simple or "titles" in ql_simple or "list" in ql_simple):
            # Extract desired count if specified
            desired_n = None
            mnum = re.search(r"\b(\d{1,3})\b", ql_simple)
            if mnum:
                try:
                    desired_n = max(1, int(mnum.group(1)))
                except Exception:
                    desired_n = None
            try:
                payloads = qdrant_service.list_chapters(tenant_id=tenant_id, limit=5000)
                chapters_map = {}
                for p in payloads:
                    num = p.get("chapter_num")
                    title = p.get("chapter_title")
                    if isinstance(num, int) and isinstance(title, str) and title:
                        # Keep the first seen title per chapter number
                        if num not in chapters_map:
                            chapters_map[num] = title
                # Fallback to SQL if empty
                if not chapters_map and db is not None:
                    q = (
                        db.query(KnowledgeChunk)
                        .join(Document, KnowledgeChunk.document_id == Document.id)
                        .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
                        .filter(KnowledgeBase.tenant_id == tenant_id)
                    )
                    for kc in q:
                        meta = kc.meta or {}
                        if isinstance(meta, dict):
                            n = meta.get("chapter_num")
                            t = meta.get("chapter_title")
                            if isinstance(n, int) and isinstance(t, str) and t and n not in chapters_map:
                                chapters_map[n] = t
                if chapters_map:
                    ordered = sorted(chapters_map.items(), key=lambda x: x[0])
                    if desired_n is not None:
                        ordered = ordered[:desired_n]
                    # Cap list length to avoid overly long answers
                    ordered = ordered[:20]
                    bullets = "\n".join([f"- Chapter {n}: {t}" for n, t in ordered])
                    response = bullets if bullets else "I don’t have that information in the current database."
                    result = {"response": response, "citations": [], "confidence": 0.75 if bullets else 0.0, "requiresHuman": False if bullets else True}
                    redis_cache.set_tenant_key(tenant_id, cache_key, result, ttl=self.cache_ttl_seconds)
                    if reranking_info:
                        result["reranking"] = reranking_info
                    return result
            except Exception:
                # fall back to generic path below
                pass

        # Chapter summary request (e.g., "summary of chapter 1")
        m_sum = re.search(r"summary\s+of\s+chapter\s+(\d+)", ql_simple)
        if retrieval.rules_enabled and m_sum:
            try:
                ch = int(m_sum.group(1))
            except Exception:
                ch = None
            if ch is not None:
                # gather contexts focused on that chapter
                focused: List[str] = []
                try:
                    # Prefer vector store payload filter via scroll
                    payloads = qdrant_service.list_chapters(tenant_id=tenant_id, limit=5000)
                    # We don't have direct content in list_chapters; augment via general search with the chapter constraint
                    cand = []
                    for c in contexts:
                        # heuristic: favor chunks whose meta was tagged earlier
                        if f"chapter {ch}" in c.lower():
                            cand.append(c)
                    focused = cand[:8] if cand else contexts[:8]
                except Exception:
                    focused = contexts[:8]
                # Compose a short summary prompt over focused contexts
                focus_text = "\n\n".join(focused)
                if self.openai_client:
                    base_prompt3 = (
                        "Summarize the key points of Chapter " + str(ch) +
                        " using only the provided CONTEXT. Keep it concise (5-7 bullet points)."
                    )
                    try:
                        completion3 = self.openai_client.chat.completions.create(
                            model=self.chat_model,
                            temperature=self.chat_temperature,
                            messages=[
                                {"role": "system", "content": "You answer using only the provided CONTEXT."},
                                {"role": "user", "content": f"CONTEXT:\n{focus_text}"},
                                {"role": "user", "content": base_prompt3},
                            ],
                        )
                        gen3 = (completion3.choices[0].message.content or "").strip()
                        if gen3:
                            result_sum = {"response": gen3, "citations": [], "confidence": 0.8, "requiresHuman": False}
                            redis_cache.set_tenant_key(tenant_id, cache_key, result_sum, ttl=self.cache_ttl_seconds)
                            return result_sum
                    except Exception:
                        pass

        # Simple table aggregation patterns (can be disabled)
        m_total = re.search(r"total\s+(sales|amount|revenue)[^\d]*(\d{4})[^\w]+in\s+([\w\s]+)$", ql_simple)
        if retrieval.rules_enabled and m_total:
            metric = m_total.group(1)
            year = m_total.group(2)
            sheet = m_total.group(3).strip()
            # Heuristic: pull contexts mentioning the sheet name or the year
            filtered = [c for c in contexts if sheet.lower() in c.lower() or year in c]
            if not filtered:
                filtered = contexts
            # Ask the LLM to compute the total from provided rows
            focus_text = "\n".join(filtered[:20])
            if self.openai_client:
                try:
                    completion4 = self.openai_client.chat.completions.create(
                        model=self.chat_model,
                        temperature=0,
                        messages=[
                            {"role": "system", "content": "You are a precise calculator. Sum only values matching the YEAR and SHEET hint."},
                            {"role": "user", "content": f"YEAR={year}; SHEET={sheet}; ROWS:\n{focus_text}\n\nReturn only the numeric total prefixed with 'Total: '"},
                        ],
                    )
                    out = (completion4.choices[0].message.content or "").strip()
                    if out:
                        result_sum2 = {"response": out, "citations": citations[:3], "confidence": 0.7, "requiresHuman": False}
                        redis_cache.set_tenant_key(tenant_id, cache_key, result_sum2, ttl=self.cache_ttl_seconds)
                        return result_sum2
                except Exception:
                    pass

        # Apply semantic interpreter to contexts before final prompting
        semantic_applied = False
        try:
            from .semantic_interpreter import SemanticContextInterpreter
            # Build per-tenant synonyms dictionary from schema_fields (dynamic)
            from shared.cache.synonyms_store import SynonymsStore
            persisted = SynonymsStore.get_all(tenant_id)
            synonyms_map = dict(persisted)
            for f in (fields_for_filter or []):
                base = str(f).strip().lower().replace("_", " ")
                if not base:
                    continue
                # map canonical to itself
                if base not in synonyms_map:
                    synonyms_map[base] = base
            interpreter = SemanticContextInterpreter(synonyms_map=synonyms_map)
            # Determine relevant schema fields for this query
            try:
                nearest_fields = self._nearest_schema_fields(query, tenant_id, top_k=8)
            except Exception:
                nearest_fields = []
            tenant_fields = self._get_schema_fields_for_tenant(tenant_id)
            fields_for_filter = nearest_fields or tenant_fields
            interpreted = interpreter.interpret(query, contexts, fields_for_filter, synonyms_map=synonyms_map)
            if interpreted and any(s.strip() for s in interpreted):
                # Deduplicate and compress interpreted paragraphs
                intent_local = self._classify_intent(query)
                unique: List[str] = []
                seen = set()
                for para in interpreted:
                    p = (para or "").strip()
                    if not p:
                        continue
                    if p.lower() in seen:
                        continue
                    seen.add(p.lower())
                    # Compress by keeping first 1-2 sentences depending on intent
                    parts = [x.strip() for x in re.split(r"(?<=[.!?])\s+", p) if x.strip()]
                    if intent_local in ("yes_no", "temporal"):
                        p_comp = parts[0] if parts else p
                    else:
                        p_comp = " ".join(parts[:2]) if parts else p
                    unique.append(p_comp)
                    # Keep only top few interpreted facts to reduce token waste
                    if len(unique) >= min(12, getattr(retrieval, 'rerank_top_k', 12)):
                        break
                # Second pass: sentence-level relevance selection
                try:
                    all_sents: List[str] = []
                    for para in unique:
                        all_sents.extend([x.strip() for x in re.split(r"(?<=[.!?])\s+", para) if x.strip()])
                    # Deduplicate sentences case-insensitively
                    seen_sent = set(); sents_dedup: List[str] = []
                    for s in all_sents:
                        sl = s.lower()
                        if sl in seen_sent:
                            continue
                        seen_sent.add(sl)
                        sents_dedup.append(s)
                    # Score sentences with BM25 against normalized query
                    if sents_dedup:
                        bm_scorer = StandardBM25([self._normalize_text(s) for s in sents_dedup])
                        s_scores = bm_scorer.score(self._normalize_text(query))
                        ranked = sorted([(sc, s) for sc, s in zip(s_scores, sents_dedup)], key=lambda x: x[0], reverse=True)
                        # Keep top sentences constrained by intent/token budget
                        if intent_local in ("yes_no", "temporal"):
                            keep_n = 4
                        elif intent_local == "causal":
                            keep_n = 8
                        else:
                            keep_n = min(20, getattr(retrieval, 'rerank_top_k', 12) * 2)
                        best_sents = [s for _sc, s in ranked[:keep_n]]
                        # Re-assemble into compact paragraphs (chunks of 2-3)
                        compact: List[str] = []
                        buf: List[str] = []
                        for s in best_sents:
                            buf.append(s)
                            if len(buf) >= 3:
                                compact.append(" ".join(buf))
                                buf = []
                        if buf:
                            compact.append(" ".join(buf))
                        unique = compact or unique
                except Exception:
                    pass
                context_text = "\n\n".join(unique)
                # Persist any newly observed alias→canonical mappings discovered by interpreter normalization
                try:
                    # Persist alias→canonical learned this run
                    learned = interpreter.get_learned_mappings()
                    if learned:
                        SynonymsStore.put_many(tenant_id, learned)
                except Exception:
                    pass
                semantic_applied = True
                try:
                    logger.info(f"semantic_interpreter applied: kept={len(unique)} intent={intent_local}")
                except Exception:
                    pass
            else:
                context_text = "\n\n".join(contexts)
                try:
                    logger.info("semantic_interpreter fallback: empty interpretation; using raw contexts")
                except Exception:
                    pass
        except Exception:
            context_text = "\n\n".join(contexts)
            try:
                logger.info("semantic_interpreter exception; using raw contexts")
            except Exception:
                pass

        # Confidence scoring: CrossEncoder preferred; cosine fallback
        def _estimate_confidence(query_text: str, ctxs: List[str]) -> float:
            try:
                if hasattr(self, 'reranker') and getattr(self.reranker, 'cross_encoder_available', False):
                    pairs = [(query_text, c) for c in ctxs[: min(12, len(ctxs))]]
                    scores = self.reranker.cross_encoder.predict(pairs, show_progress_bar=False)
                    return float(max(0.0, min(1.0, sum(scores) / max(1, len(scores)))))
                qemb = self._embed_with_cache(query_text)
                if not qemb:
                    return 0.0
                import math
                def cos(a, b):
                    dot = sum(x*y for x, y in zip(a, b))
                    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
                    if na == 0 or nb == 0:
                        return 0.0
                    return dot / (na * nb)
                vals = []
                for c in ctxs[: min(12, len(ctxs))]:
                    emb = self._embed_with_cache(c)
                    if emb:
                        vals.append(cos(qemb, emb))
                return float(max(0.0, min(1.0, sum(vals) / max(1, len(vals))))) if vals else 0.0
            except Exception:
                return 0.0

        interpreted_list = context_text.split("\n\n") if context_text else []
        confidence_est = _estimate_confidence(query, interpreted_list) if interpreted_list else 0.0
        low_conf_threshold = 0.5 if hasattr(self, 'reranker') and getattr(self.reranker, 'cross_encoder_available', False) else 0.3
        low_confidence = confidence_est < low_conf_threshold

        generated_text = None
        if self.openai_client:
            plan_text = json.dumps(plan, ensure_ascii=False)
            # Adjust temperature/style based on intent
            intent = self._classify_intent(query)
            temp = {
                "yes_no": 0.1,
                "temporal": 0.2,
                "causal": 0.5,
                "descriptive": self.chat_temperature,
            }.get(intent, self.chat_temperature)
            base_prompt = self.prompt_template.format(context=context_text, question=query)
            intent_directive = {
                "yes_no": "Instruction: Answer strictly yes or no with a short explicit statement (e.g., 'Yes, <Name> is married.') and nothing else.",
                "temporal": "Instruction: Return only the date in a human-readable format (e.g., 'June 1, 2015.') without extra explanation.",
                "causal": "Instruction: Provide a brief reason in one sentence.",
                "descriptive": "Instruction: Provide a 1–2 sentence concise summary; avoid raw field labels.",
            }.get(intent, "")
            prompt = base_prompt
            if intent_directive:
                prompt += "\n\n" + intent_directive
            prompt += "\n\nPLANNER_DIRECTIVE (Model-generated plan for how to answer; follow if helpful):\n" + plan_text
            try:
                if not low_confidence:
                    completion = self.openai_client.chat.completions.create(
                        model=self.chat_model,
                        temperature=temp,
                        messages=[
                            {"role": "system", "content": "You answer using only the provided CONTEXT."},
                            {"role": "user", "content": prompt},
                        ],
                    )
                    generated_text = (completion.choices[0].message.content or "").strip()
            except Exception:
                # If generation fails, fall back to concise snippet
                generated_text = None

        if not generated_text:
            # Fallback concise answer, guarded by confidence
            if low_confidence:
                generated_text = "I don’t have enough information to answer precisely."
            else:
                generated_text = f"{self.no_info_text}" if not contexts else contexts[0][:300]

        # Build grounded citations using vector hit metadata when available
        citations: List[Dict[str, Any]] = []
        try:
            if 'vector_hits_rich' in locals() and vector_hits_rich:
                for i, hit in enumerate(vector_hits_rich[:6]):
                    title = hit.get('document_title') or f"Document {i+1}"
                    chap = hit.get('chapter_title')
                    page = hit.get('page')
                    pieces = [p for p in [title, f"Chapter {hit.get('chapter_num')}" if hit.get('chapter_num') is not None else None, f"Page {page}" if page else None] if p]
                    cite_title = " • ".join(pieces) if pieces else title
                    citations.append({
                        "source": hit.get('document_id') or f"doc_{i}",
                        "title": cite_title,
                        "relevance": float(hit.get('score') or 0.8),
                        "snippet": (hit.get('content') or '')[:160],
                    })
            else:
                for i, ctx in enumerate(contexts[:6]):
                    citations.append({
                        "source": f"chunk_{i}",
                        "title": f"Context {i+1}",
                        "relevance": 0.8,
                        "snippet": ctx[:160],
                    })
        except Exception:
            for i, ctx in enumerate(contexts[:6]):
                citations.append({
                    "source": f"chunk_{i}",
                    "title": f"Context {i+1}",
                    "relevance": 0.8,
                    "snippet": ctx[:160],
                })

        result = {
            "response": generated_text,
            "citations": citations,
            "confidence": float(confidence_est) if interpreted_list else (0.9 if contexts and generated_text else 0.4),
            "requiresHuman": False if contexts else True,
        }
        if reranking_info:
            result["reranking"] = reranking_info
        # Mark whether semantic interpreter was applied
        result["context_pipeline"] = "semantic_interpreter_applied" if semantic_applied else "raw_context_fallback"
        # Semantic health logging
        try:
            health = {
                "tenant_id": tenant_id,
                "intent": intent,
                "matched_fields": list(fields_for_filter)[:10] if isinstance(fields_for_filter, list) else [],
                "semantic_applied": bool(semantic_applied),
                "confidence": float(confidence_est),
                "low_confidence": bool(low_confidence),
                "answer_type": intent,
            }
            result["health"] = health
            logger.info(f"semantic_health: {json.dumps(health, ensure_ascii=False)}")
        except Exception:
            pass
        redis_cache.set_tenant_key(tenant_id, cache_key, result, ttl=self.cache_ttl_seconds)
        # Semantic-only fallback when confidence is low
        try:
            if getattr(retrieval, 'semantic_fallback_enabled', True) and (confidence_est < 0.5):
                # Dense-only retrieval with larger top_k, including field_values
                topk_mul = max(1, int(getattr(retrieval, 'semantic_fallback_topk_multiplier', 2)))
                emb_avg2 = self._embed_queries_avg(query)
                dense_hits2 = self._qdrant_contexts_rich(query, tenant_id=tenant_id, top_k=retrieval.vector_top_k * topk_mul, emb_override=emb_avg2)
                fv_hits2 = self._qdrant_field_values_rich(query, tenant_id=tenant_id, top_k=getattr(retrieval, 'field_value_top_k', 8) * topk_mul, emb_override=emb_avg2)
                # Fuse only dense and field_values (no BM25)
                dense_texts2 = [h.get('content', '') for h in (dense_hits2 or []) if isinstance(h.get('content'), str)]
                fv_texts2 = [h.get('content', '') for h in (fv_hits2 or []) if isinstance(h.get('content'), str)]
                candidates2 = list(dict.fromkeys(dense_texts2 + fv_texts2))
                # Lightweight rerank
                contexts2, _info2 = self._apply_advanced_reranking(candidates2, dense_hits2, {}, query, activated_schema_fields=[])
                # Confidence re-estimate
                interpreted_list2 = contexts2[: min(12, len(contexts2))]
                conf2 = 0.0
                if interpreted_list2:
                    def _estimate_conf_local(qt: str, ctxs: List[str]) -> float:
                        try:
                            if hasattr(self, 'reranker') and getattr(self.reranker, 'cross_encoder_available', False):
                                pairs = [(qt, c) for c in ctxs]
                                scores = self.reranker.cross_encoder.predict(pairs, show_progress_bar=False)
                                import math as _m
                                return float(max(0.0, min(1.0, sum(scores) / max(1, len(scores)))))
                            return 0.0
                        except Exception:
                            return 0.0
                    conf2 = _estimate_conf_local(query, interpreted_list2)
                # Prefer fallback if higher confidence or we have a concrete field_value hit
                has_fv = bool(fv_hits2)
                if (conf2 > confidence_est) or has_fv:
                    # Regenerate succinct answer on improved contexts
                    ctx_text2 = "\n\n".join(contexts2[: min(12, len(contexts2))])
                    gen2 = None
                    if self.openai_client:
                        try:
                            base_p2 = self.prompt_template.format(context=ctx_text2, question=query)
                            completion2 = self.openai_client.chat.completions.create(
                                model=self.chat_model,
                                temperature=self.chat_temperature,
                                messages=[
                                    {"role": "system", "content": "You answer using only the provided CONTEXT."},
                                    {"role": "user", "content": base_p2},
                                ],
                            )
                            gen2 = (completion2.choices[0].message.content or '').strip()
                        except Exception:
                            gen2 = None
                    if gen2:
                        citations2: List[Dict[str, Any]] = []
                        for i, ctx in enumerate(contexts2[:6]):
                            citations2.append({
                                "source": f"chunk_{i}",
                                "title": f"Context {i+1}",
                                "relevance": 0.85,
                                "snippet": ctx[:160],
                            })
                        result = {
                            "response": gen2,
                            "citations": citations2,
                            "confidence": float(conf2),
                            "requiresHuman": False,
                        }
                        redis_cache.set_tenant_key(tenant_id, cache_key, result, ttl=self.cache_ttl_seconds)
                        return result
        except Exception:
            pass

        # If the model responded with the no-info string, try one iterative expansion pass
        if self.no_info_text in (generated_text or ""):
            expansions = self.expand_queries(query)
            if expansions:
                expanded_contexts: List[str] = []
                for q2 in expansions[: retrieval.expand_variants]:
                    expanded_contexts.extend(self.retriever.retrieve(q2, top_k=retrieval.vector_top_k))
                    try:
                        expanded_contexts.extend(self._qdrant_contexts(q2, tenant_id=tenant_id, top_k=retrieval.vector_top_k))
                    except Exception:
                        pass
                combined2 = expanded_contexts + contexts
                # Dedup
                seen2 = set()
                dedup2: List[str] = []
                for c in combined2:
                    k = c[:200].lower()
                    if k in seen2:
                        continue
                    seen2.add(k)
                    dedup2.append(c)
                dedup2 = self.rerank_contexts_via_llm(query, dedup2, top_k=12)
                if dedup2:
                    context_text2 = "\n\n".join(dedup2)
                    if self.openai_client:
                        base_prompt2 = self.prompt_template.format(context=context_text2, question=query)
                        prompt2 = base_prompt2 + "\n\nPLANNER_DIRECTIVE (Model-generated plan for how to answer; follow if helpful):\n" + plan_text
                        try:
                            completion2 = self.openai_client.chat.completions.create(
                                model=self.chat_model,
                                temperature=self.chat_temperature,
                                messages=[
                                    {"role": "system", "content": "You answer using only the provided CONTEXT."},
                                    {"role": "user", "content": prompt2},
                                ],
                            )
                            generated2 = (completion2.choices[0].message.content or "").strip()
                            if generated2 and self.no_info_text not in generated2:
                                citations2 = []
                                for i, ctx in enumerate(dedup2[:6]):
                                    citations2.append({
                                        "source": f"chunk_{i}",
                                        "title": f"Context {i+1}",
                                        "relevance": 0.85,
                                        "snippet": ctx[:160],
                                    })
                                result2 = {
                                    "response": generated2,
                                    "citations": citations2,
                                    "confidence": 0.9,
                                    "requiresHuman": False,
                                }
                                redis_cache.set_tenant_key(tenant_id, cache_key, result2, ttl=self.cache_ttl_seconds)
                                return result2
                        except Exception:
                            pass
                    # As last resort, return a concise best snippet
                    if dedup2:
                        snippet = dedup2[0][:300]
                        result3 = {
                            "response": snippet,
                            "citations": citations,
                            "confidence": 0.6,
                            "requiresHuman": False,
                        }
                        redis_cache.set_tenant_key(tenant_id, cache_key, result3, ttl=self.cache_ttl_seconds)
                        return result3
        if reranking_info:
            result["reranking"] = reranking_info
        return result


    def _get_bi_encoder_scores(self, query: str, contexts: List[str], 
                              vector_hits_rich: List[Dict[str, Any]]) -> List[float]:
        """Get BiEncoder scores from vector search results."""
        scores = [1.0] * len(contexts)  # Default scores
        
        if not vector_hits_rich:
            return scores
        
        # Create content to score mapping
        content_to_score = {}
        for hit in vector_hits_rich:
            content = hit.get('content', '')
            score = hit.get('score', 0.0)
            if content:
                content_to_score[content] = score
        
        # Match scores for each context
        for i, context in enumerate(contexts):
            # Try exact match
            if context in content_to_score:
                scores[i] = content_to_score[context]
            else:
                # Try partial match
                for content, score in content_to_score.items():
                    if context in content or content in context:
                        scores[i] = max(scores[i], score * 0.8)  # Partial match discount
                        break
        
        return scores
 
    def toggle_reranker(self, enabled: bool = None) -> bool:
        """Toggle reranker on/off."""
        if enabled is not None:
            self.reranker_enabled = bool(enabled)
            # Reflect in process env config-like state if needed by other components
            try:
                os.environ["RERANK_ENABLED"] = "true" if self.reranker_enabled else "false"
            except Exception:
                pass
            logger.info(f"Reranker {'enabled' if self.reranker_enabled else 'disabled'}")
        return self.reranker_enabled
 
    def get_reranker_status(self) -> Dict[str, Any]:
        """Get reranker status and configuration."""
        return {
            "enabled": self.reranker_enabled,
            "model_info": self.reranker.get_model_info(),
            "config": {
                "ltr_enabled": reranker_config.ltr_enabled,
                "cache_enabled": reranker_config.cache_enabled,
                "cross_encoder_model": reranker_config.cross_encoder_model,
                "enabled_flag": reranker_config.enabled,
            }
        }
 
    def clear_reranker_cache(self):
        """Clear reranker caches."""
        self.reranker.clear_cache()
        logger.info("Reranker caches cleared")
 
    async def shutdown(self):
        """Cleanup resources."""
        if hasattr(self, 'reranker'):
            try:
                self.reranker.clear_cache()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")