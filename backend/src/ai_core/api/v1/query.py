"""
Query API router integrating conversation and RAG services.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ai_core.models.message import QueryRequest, QueryResponse
from ai_core.services.conversation_service import ConversationService
from ai_core.services.rag_service import RAGService
from ai_core.services.document_service import DocumentService
from shared.database.session import get_db
from shared.database.models import KnowledgeChunk, Document, KnowledgeBase
import csv, io
import uuid
import numpy as np
import re

router = APIRouter(prefix="/v1", tags=["query"])

rag_service = RAGService()


@router.post("/query", response_model=QueryResponse)
def post_query(payload: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    if not payload.tenant_id or not payload.message or not payload.channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: tenantId, message, channel",
        )

    # Validate/convert UUIDs for DB compatibility
    try:
        tenant_uuid = uuid.UUID(str(payload.tenant_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tenantId UUID")

    user_uuid = None
    if payload.user_id:
        try:
            user_uuid = uuid.UUID(str(payload.user_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid userId UUID")
    else:
        user_uuid = uuid.uuid4()

    # Sensitive attribute inference guard
    lower_q = payload.message.lower()
    sensitive_terms = ["ethnic", "ethnicity", "race", "hispanic", "religion", "sexual orientation"]
    if any(term in lower_q for term in sensitive_terms):
        safe = {
            "response": "I can’t determine or infer a person’s protected characteristics. Please consult appropriate, consented records or escalate to a human agent.",
            "citations": [],
            "confidence": 0.0,
            "requiresHuman": True,
        }
        return QueryResponse(**safe)

    conversation_service = ConversationService(db)
    # Ensure UUID types where required by DB models: use deterministic UUIDs for test if missing
    conversation = conversation_service.get_or_create_conversation(
        tenant_id=tenant_uuid,
        user_id=user_uuid,
        channel=payload.channel,
        context=payload.context,
    )
    conversation_service.add_message(conversation, sender_type="USER", content=payload.message)

    # Helpers for normalization and matching
    def norm_col(s: str) -> str:
        s = s.strip().lower().replace('\ufeff', '')
        s = re.sub(r"[^a-z0-9]+", "_", s)
        return s.strip('_')

    def norm_name(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower().replace('\ufeff',''))

    def name_variants(raw: str):
        n = norm_name(raw)
        variants = {n}
        if "," in raw:
            parts2 = [p.strip() for p in raw.replace('\ufeff','').split(',')]
            if len(parts2) >= 2:
                variants.add(norm_name(f"{parts2[1]} {parts2[0]}"))
        return variants

    # Build tenant-specific corpus with associated columns metadata when available
    rows = (
        db.query(KnowledgeChunk.content, KnowledgeChunk.embedding, Document.meta)
        .join(Document, KnowledgeChunk.document_id == Document.id)
        .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
        .filter(KnowledgeBase.tenant_id == tenant_uuid)
        .order_by(KnowledgeChunk.created_at.desc())
        .limit(2000)
        .all()
    )
    corpus = [content for (content, _emb, _meta) in rows]
    row_embeddings = [emb for (_content, emb, _meta) in rows]
    corpus_columns = []
    for (_content, _emb, meta) in rows:
        cols = None
        if isinstance(meta, dict) and 'columns' in meta and isinstance(meta['columns'], list):
            cols = [norm_col(str(c)) for c in meta['columns']]
        corpus_columns.append(cols)

    if not corpus:
        no_knowledge = {
            "response": "No tenant knowledge available yet to answer this question. Please upload documents or escalate to a human agent.",
            "citations": [],
            "confidence": 0.0,
            "requiresHuman": True,
        }
        conversation_service.add_message(conversation, sender_type="SYSTEM", content=no_knowledge["response"])
        return QueryResponse(**no_knowledge)

    # Index and retrieve candidates
    rag_service.retriever.index(corpus)
    candidates = rag_service.retriever.retrieve(payload.message, top_k=10)

    # Schema-aware extraction for tabular rows
    def detect_requested_field(q: str):
        ql = q.lower()
        mapping = {
            'salary': ['salary', 'annualsalary', 'salaryamount', 'pay'],
            'department': ['department', 'dept'],
            'manager': ['manager', 'managername'],
            'employmentstatus': ['employmentstatus', 'status'],
        }
        for key, terms in mapping.items():
            if any(t in ql for t in terms):
                return key
        return None

    def parse_csv_row(row_text: str):
        reader = csv.reader(io.StringIO(row_text))
        return next(reader)

    requested = detect_requested_field(payload.message)
    if requested:
        person_match = re.search(r"(?:of|for)\s+([^?]+)", payload.message, flags=re.IGNORECASE)
        person_name_raw = person_match.group(1) if person_match else payload.message
        person_name_raw = person_name_raw.strip().strip('?')
        person_names = name_variants(person_name_raw)

        field_aliases = {
            'salary': ['salary', 'annualsalary', 'salaryamount', 'pay', 'basepay', 'base_salary'],
            'department': ['department', 'dept'],
            'manager': ['manager', 'managername'],
            'employmentstatus': ['employmentstatus', 'status'],
        }

        # Compute embedding similarity to rank candidates
        emb_service = DocumentService(db)
        qvec = np.array(emb_service.embed([payload.message])[0], dtype=float)

        best_value = None
        best_row_text = None
        best_sim = -1.0
        for i, cand in enumerate(corpus):
            cols = corpus_columns[i]
            if not cols:
                continue
            values = parse_csv_row(cand)
            col_to_val = {cols[j]: values[j] if j < len(values) else '' for j in range(len(cols))}
            # Determine row name
            name_cols = ['employee_name', 'name', 'employee', 'empname', 'full_name', 'employee_full_name']
            row_name = None
            for nc in name_cols:
                if nc in col_to_val and str(col_to_val[nc]).strip() != '':
                    row_name = norm_name(str(col_to_val[nc]))
                    break
            if row_name:
                if row_name not in {norm_name(v) for v in person_names}:
                    continue
            else:
                # Fallback: attempt to find exact full-name match in any cell
                row_match = False
                person_norms = {norm_name(v) for v in person_names}
                for v in values:
                    if norm_name(str(v)) in person_norms:
                        row_match = True
                        break
                if not row_match:
                    continue
            # Extract requested field
            for key in field_aliases.get(requested, []):
                k = norm_col(key)
                if k in col_to_val and str(col_to_val[k]).strip() != '':
                    rvec = np.array(row_embeddings[i], dtype=float)
                    denom = (np.linalg.norm(qvec) * np.linalg.norm(rvec)) or 1.0
                    sim = float(np.dot(qvec, rvec) / denom)
                    if sim > best_sim:
                        best_sim = sim
                        best_value = str(col_to_val[k]).strip()
                        best_row_text = cand
                    break
        if best_value:
            response_payload = {
                "response": f"{requested.capitalize()}: {best_value}",
                "citations": [{"source": "row", "title": "Matched record", "relevance": 0.99, "snippet": best_row_text[:160]}],
                "confidence": 0.9,
                "requiresHuman": False,
            }
            conversation_service.add_message(conversation, sender_type="SYSTEM", content=response_payload["response"])
            return QueryResponse(**response_payload)
        # Avoid falling back to generic RAG when a specific field was requested but not found
        no_match = {
            "response": "No matching record found for the requested person and field. Please confirm the name spelling and column headers (e.g., Employee_Name, Salary).",
            "citations": [],
            "confidence": 0.0,
            "requiresHuman": True,
        }
        conversation_service.add_message(conversation, sender_type="SYSTEM", content=no_match["response"])
        return QueryResponse(**no_match)

    # Fallback to generic RAG answer if no structured match
    result = rag_service.answer(payload.message)
    conversation_service.add_message(conversation, sender_type="SYSTEM", content=result["response"])
    return QueryResponse(**result)


