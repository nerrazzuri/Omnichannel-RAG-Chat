"""
RAG service with hybrid retrieval (BM25 + dense vectors) and RRF fusion,
augmented with OpenAI chat generation using a strict prompt to avoid
hallucinations.
"""
from typing import List, Dict, Any, Optional
import difflib
from datetime import datetime
from collections import defaultdict
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

# Placeholder lightweight BM25 implementation using term frequency
class BM25Lite:
    def __init__(self, docs: List[str]):
        self.docs = docs
        self.doc_count = len(docs)
        self.avgdl = sum(len(d.split()) for d in docs) / max(1, self.doc_count)

    def score(self, query: str, k1: float = 1.5, b: float = 0.75) -> List[float]:
        q_terms = query.lower().split()
        scores = []
        for d in self.docs:
            terms = d.lower().split()
            dl = len(terms)
            tf = defaultdict(int)
            for t in terms:
                tf[t] += 1
            score = 0.0
            for qt in q_terms:
                f = tf.get(qt, 0)
                if f == 0:
                    continue
                idf = math.log((self.doc_count - 1 + 0.5) / (1 + 0.5))  # simple idf approx
                score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / max(1, self.avgdl)))
            scores.append(score)
        return scores


class HybridRetriever:
    def __init__(self):
        # In a real system: load vector store client (e.g., Qdrant) and embeddings
        self.corpus = []
        self.bm25 = None

    def index(self, documents: List[str]) -> None:
        self.corpus = documents[:]
        self.bm25 = BM25Lite(self.corpus)

    def dense_search(self, query: str, top_k: int = 5) -> List[int]:
        # Improved scoring with both length and content similarity
        q_len = len(query)
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored = []
        for i, doc in enumerate(self.corpus):
            doc_lower = doc.lower()
            doc_words = set(doc_lower.split())
            
            # Calculate Jaccard similarity for word overlap
            intersection = len(query_words & doc_words)
            union = len(query_words | doc_words)
            jaccard = intersection / max(1, union)
            
            # Length similarity (normalized)
            length_sim = 1.0 / (1.0 + abs(len(doc) - q_len) / max(q_len, 1))
            
            # Combined score with emphasis on content similarity
            score = (jaccard * 2.0) + length_sim
            scored.append((i, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [i for i, _ in scored[:top_k]]

    def keyword_search(self, query: str, top_k: int = 5) -> List[int]:
        if not self.bm25:
            self.bm25 = BM25Lite(self.corpus)
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

    def rrf_fuse(self, lists: List[List[int]], k: int = 60, top_k: int = 5) -> List[int]:
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
        self.chat_model = os.getenv("RAG_CHAT_MODEL", "gpt-4o-mini")
        self.chat_temperature = float(os.getenv("RAG_CHAT_TEMPERATURE", "0.3"))
        # Strict prompt to keep answers grounded
        self.prompt_template = (
            "You are a professional corporate assistant with access to internal company documents. Your name is Omni.\n\n"
            "Use the information from the CONTEXT below to answer the QUESTION as accurately and helpfully as possible.\n"
            "If the context truly lacks the relevant information, reply exactly with: \n"
            "\"I don’t have that information in the current database.\"\n\n"
            "Always include short source citations at the end.\n\n"
            "---\nCONTEXT:\n{context}\n---\nQUESTION:\n{question}\n---\nAnswer:"
        )
        self.no_info_text = "I don’t have that information in the current database."

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

    def expand_queries(self, query: str) -> List[str]:
        """Use the LLM to generate a small set of reformulations to broaden retrieval."""
        expansions: List[str] = []
        if not self.openai_client:
            return expansions
        try:
            prompt = (
                "Rewrite the user's question into 3 to 5 alternative phrasings that preserve the meaning, one per line.\n"
                "Focus on synonyms, explicit topic names, and removing pronouns.\n"
                f"USER QUESTION: {query}"
            )
            completion = self.openai_client.chat.completions.create(
                model=os.getenv("RAG_EXPAND_MODEL", self.chat_model),
                temperature=0.3,
                messages=[
                    {"role": "system", "content": "You generate alternative search queries only."},
                    {"role": "user", "content": prompt},
                ],
            )
            text = (completion.choices[0].message.content or "").strip()
            for line in text.splitlines():
                s = line.strip("- *\t ")
                if s and s.lower() != query.lower() and s not in expansions:
                    expansions.append(s)
            return expansions[:5]
        except Exception:
            return []

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
            resp = self.openai_client.embeddings.create(
                model=os.getenv("RAG_EMBED_MODEL", "text-embedding-3-small"),
                input=[text],
            )
            return resp.data[0].embedding
        except Exception:
            return None

    def _qdrant_contexts(self, query: str, tenant_id: str, top_k: int = 6) -> list[str]:
        emb = self._embed_query(query)
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

    def _qdrant_contexts_rich(self, query: str, tenant_id: str, top_k: int = 6) -> List[Dict[str, Any]]:
        emb = self._embed_query(query)
        if not emb:
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
        # Cache by query text across tenants in a simple way; tenant aware cache keys should be added at call site if needed
        cache_key = f"rag:answer:{tenant_id}:{hash(query)}"
        cached = redis_cache.get_tenant_key(tenant_id, cache_key)
        if isinstance(cached, dict) and cached.get("response"):
            return cached

        # Identity questions: respond as Omni
        ql_id = (query or "").strip().lower()
        if any(p in ql_id for p in ["what is your name", "what's your name", "who are you", "your name", "what is ur name", "name please", "what are you called"]):
            result_id = {"response": "My name is Omni.", "citations": [], "confidence": 0.99, "requiresHuman": False}
            redis_cache.set_tenant_key(tenant_id, cache_key, result_id, ttl=self.cache_ttl_seconds)
            return result_id

        contexts = preselected_contexts if preselected_contexts is not None else self.retriever.retrieve(query, top_k=retrieval.hybrid_top_k)
        # Augment with vector search (Qdrant) when embeddings are available
        try:
            vector_hits_rich = self._qdrant_contexts_rich(query, tenant_id=tenant_id, top_k=retrieval.vector_top_k)
        except Exception:
            vector_hits_rich = []
        # Stitch adjacent chunks for vector results
        stitched_texts: List[str] = []
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
                    # Assemble neighbors around the hit, ordered by chunk_index
                    all_parts = []
                    # include previous neighbors
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
            vector_hits = [h.get("content", "") for h in vector_hits_rich if isinstance(h.get("content"), str)]
        else:
            vector_hits = []

        if vector_hits or stitched_texts:
            combined = contexts + stitched_texts + vector_hits
            # Deduplicate while preserving order
            seen = set()
            dedup: list[str] = []
            for c in combined:
                k = c[:200].lower()
                if k in seen:
                    continue
                seen.add(k)
                dedup.append(c)
            contexts = dedup[:20]
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

        context_text = "\n\n".join(contexts)

        generated_text = None
        if self.openai_client:
            plan_text = json.dumps(plan, ensure_ascii=False)
            base_prompt = self.prompt_template.format(context=context_text, question=query)
            prompt = base_prompt + "\n\nPLANNER_DIRECTIVE (Model-generated plan for how to answer; follow if helpful):\n" + plan_text
            try:
                completion = self.openai_client.chat.completions.create(
                    model=self.chat_model,
                    temperature=self.chat_temperature,
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
            # Fallback concise answer mirroring sample formatting
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
            "confidence": 0.9 if contexts and generated_text else 0.4,
            "requiresHuman": False if contexts else True,
        }
        redis_cache.set_tenant_key(tenant_id, cache_key, result, ttl=self.cache_ttl_seconds)
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
        return result


