from typing import List, Dict, Any, Tuple

from shared.database.models import KnowledgeChunk, Document, KnowledgeBase
from shared.config.tuning import retrieval
from ai_core.pipeline.fusion.bm25 import StandardBM25


class BM25Retriever:
    def build_corpus(
        self,
        db,
        tenant_id: str,
        limit: int = 2000,
    ) -> Tuple[List[str], List[str], Dict[str, str], Dict[str, Dict[str, str]], Dict[str, str]]:
        """Return (corpus_texts, idx_to_id, id_to_content, content_to_row, sig_to_id)."""
        q = (
            db.query(KnowledgeChunk, Document, KnowledgeBase)
            .join(Document, KnowledgeChunk.document_id == Document.id)
            .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .filter(KnowledgeBase.tenant_id == tenant_id)
        )
        corpus_cap = min(int(limit), int(getattr(retrieval, 'bm25_corpus_limit', 2000)))
        tenant_pairs = q.limit(corpus_cap).all()
        id_to_content: Dict[str, str] = {}
        content_to_row: Dict[str, Dict[str, str]] = {}
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
                        # normalize to str->str
                        content_to_row[c] = {str(k): str(v) for k, v in rowm.items() if v is not None}
                except Exception:
                    pass
        return corpus_texts, idx_to_id, id_to_content, content_to_row, sig_to_id

    def rank_texts(self, query: str, corpus_texts: List[str], top_k: int = 30) -> List[Tuple[int, float]]:
        if not corpus_texts:
            return []
        bm25 = StandardBM25(corpus_texts)
        scores = bm25.score(query)
        ranked = sorted([(i, s) for i, s in enumerate(scores)], key=lambda x: x[1], reverse=True)
        return ranked[:top_k]



