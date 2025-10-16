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
    # Load mutable conversation context (persist short-term memory like last person asked)
    convo_ctx = dict(conversation.context or {})

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

    def looks_like_person(raw: str) -> bool:
        if not raw:
            return False
        s = raw.strip()
        sl = s.lower()
        # Exclude obvious non-person topics
        non_person_keywords = [
            'chapter', 'program', 'project', 'management', 'roles', 'responsibilities',
            'governance', 'policy', 'process', 'procedure', 'guideline'
        ]
        if any(k in sl for k in non_person_keywords):
            return False
        # Disallow digits-heavy strings
        if re.search(r"\d", s):
            return False
        # Accept formats: "Last, First" or "First Last [Middle]?"
        if "," in s and len(s.split(",")) >= 2:
            return True
        tokens = [t for t in s.split() if t]
        return 2 <= len(tokens) <= 4

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

    # Chapter navigation: answer "next chapter after chapter N"
    def detect_next_chapter_request(q: str):
        ql = q.lower()
        m = re.search(r"next\s+chapter\s+after\s+chapter\s+(\d+)", ql)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
        return None

    def extract_chapters(texts: list[str]) -> dict[int, str]:
        found: dict[int, str] = {}
        for t in texts:
            for line in t.splitlines():
                s = line.strip()
                if not s:
                    continue
                m = re.match(r"^chapter\s+(\d+)\s*[\.:\-]?\s*(.*)$", s, flags=re.IGNORECASE)
                if m:
                    try:
                        num = int(m.group(1))
                        title = m.group(2).strip()
                        if num not in found and title:
                            found[num] = title
                    except Exception:
                        continue
        return found

    base_ch = detect_next_chapter_request(payload.message)
    if base_ch is not None:
        top_texts = [corpus[i] for i in (candidates[:8] if candidates else [])]
        chapters = extract_chapters(top_texts if top_texts else corpus)
        if (base_ch + 1) in chapters:
            next_num = base_ch + 1
            next_title = chapters[next_num]
            # Persist simple chapter memory
            try:
                convo_ctx['last_chapter'] = next_num
                convo_ctx['last_chapter_title'] = next_title
                conversation.context = convo_ctx
                db.add(conversation)
                db.commit()
                db.refresh(conversation)
            except Exception:
                db.rollback()
            reply = {
                "response": f"The next chapter is Chapter {next_num}: {next_title}.",
                "citations": [],
                "confidence": 0.9,
                "requiresHuman": False,
            }
            conversation_service.add_message(conversation, sender_type="SYSTEM", content=reply["response"])
            return QueryResponse(**reply)
        else:
            no_next = {
                "response": "I couldn’t find the next chapter title in the uploaded content.",
                "citations": [],
                "confidence": 0.0,
                "requiresHuman": True,
            }
            conversation_service.add_message(conversation, sender_type="SYSTEM", content=no_next["response"])
            return QueryResponse(**no_next)

    # Ordered-list extraction and follow-up memory (e.g., project management processes)
    def detect_list_request(q: str):
        ql = q.lower().strip()
        # Patterns: "first 3 ... of <topic>", "top 3 ... in <topic>", "next 5", "subsequent 5 ... of <topic>"
        m_first = re.search(r"\b(first|top)\s+(\d+)\b.*?(?:of|in)\s+(.+)$", ql)
        if m_first:
            n = int(m_first.group(2))
            topic = m_first.group(3).strip().rstrip('?').strip()
            return {"mode": "first", "n": n, "topic": topic}
        m_next = re.search(r"\b(next|subsequent)\s+(\d+)\b(?:.*?(?:of|in)\s+(.+))?", ql)
        if m_next:
            n = int(m_next.group(2))
            topic = m_next.group(3).strip().rstrip('?').strip() if m_next.group(3) else None
            return {"mode": "next", "n": n, "topic": topic}
        return None

    def extract_ordered_items(texts: list[str]) -> list[str]:
        items: list[str] = []
        for t in texts:
            for line in t.splitlines():
                s = line.strip()
                if not s:
                    continue
                if re.match(r"^(?:[-*•]\s+|\d+[\.)]\s+)", s):
                    # Remove bullet/number prefix
                    s = re.sub(r"^(?:[-*•]\s+|\d+[\.)]\s+)", "", s).strip()
                    if s and s not in items:
                        items.append(s)
        return items

    list_req = detect_list_request(payload.message)
    if list_req:
        topic = list_req.get("topic") or convo_ctx.get("last_list_topic")
        if not topic:
            no_topic = {
                "response": "Which topic are you referring to? For example: ‘first 3 processes of project management’.",
                "citations": [],
                "confidence": 0.0,
                "requiresHuman": False,
            }
            conversation_service.add_message(conversation, sender_type="SYSTEM", content=no_topic["response"])
            return QueryResponse(**no_topic)

        # Gather top candidate texts as source for list extraction
        top_texts = [corpus[i] for i in (candidates[:6] if candidates else [])]
        items = extract_ordered_items(top_texts)

        # If we had a previous list and same topic, reuse items as source of truth
        if convo_ctx.get("last_list_topic") == topic and isinstance(convo_ctx.get("last_list_items"), list):
            prev_items = [it for it in convo_ctx.get("last_list_items") if isinstance(it, str) and it]
            # Prefer the longer list between prev and freshly extracted
            if len(prev_items) > len(items):
                items = prev_items

        if not items:
            no_items = {
                "response": f"I couldn’t find an ordered list of items for {topic}.",
                "citations": [],
                "confidence": 0.0,
                "requiresHuman": True,
            }
            conversation_service.add_message(conversation, sender_type="SYSTEM", content=no_items["response"])
            return QueryResponse(**no_items)

        n = max(1, int(list_req.get("n", 1)))
        mode = list_req.get("mode")
        start_index = 0
        if mode == "next":
            # Continue from prior index if same topic
            if convo_ctx.get("last_list_topic") == topic and isinstance(convo_ctx.get("last_list_index"), int):
                start_index = max(0, int(convo_ctx["last_list_index"]))

        end_index = min(len(items), start_index + n)
        slice_items = items[start_index:end_index]

        # Persist list memory
        try:
            convo_ctx["last_list_topic"] = topic
            convo_ctx["last_list_items"] = items
            convo_ctx["last_list_index"] = end_index
            conversation.context = convo_ctx
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        except Exception:
            db.rollback()

        numbered = [f"{i+1}. {it}" for i, it in enumerate(slice_items, start=start_index)]
        response_text = f"Here are the {'next' if mode=='next' else 'first'} {len(slice_items)} items for {topic}:\n" + "\n".join(numbered)
        payload_out = {
            "response": response_text,
            "citations": [],
            "confidence": 0.8,
            "requiresHuman": False,
        }
        conversation_service.add_message(conversation, sender_type="SYSTEM", content=payload_out["response"])
        return QueryResponse(**payload_out)

    # Schema-aware extraction for tabular rows
    def detect_requested_field(q: str):
        ql = q.lower()
        mapping = {
            'salary': ['salary', 'annualsalary', 'salaryamount', 'pay', 'compensation', 'wage', 'earning'],
            'department': ['department', 'dept', 'division', 'team', 'unit'],
            'manager': ['manager', 'managername', 'supervisor', 'boss', 'reports to', 'reporting manager'],
            'employmentstatus': ['employmentstatus', 'status', 'employment status', 'work status'],
            'position': ['position', 'title', 'job title', 'role', 'designation'],
            'location': ['location', 'office', 'site', 'workplace', 'based in'],
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
        candidate = person_match.group(1).strip() if person_match else None
        pronoun_ref = any(p in lower_q for p in ["his", "her", "their", "him", "them"])
        # Determine person context: either pronoun referring to memory, or the captured phrase looks like a person
        person_context = (pronoun_ref and 'last_person' in convo_ctx) or (candidate and looks_like_person(candidate))
        if not person_context:
            # Not a person-specific query; answer via generic RAG/policy and return
            preselected_np = candidates[:6] if candidates else []
            result_np = rag_service.answer(payload.message, preselected_contexts=preselected_np)
            conversation_service.add_message(conversation, sender_type="SYSTEM", content=result_np["response"])
            return QueryResponse(**result_np)
        else:
            person_name_raw = candidate if candidate else convo_ctx.get('last_person')
            if not person_name_raw:
                no_person = {
                    "response": "Who are you asking about? Please include the person’s name (e.g., ‘What is the position of Jane Doe?’).",
                    "citations": [],
                    "confidence": 0.0,
                    "requiresHuman": False,
                }
                conversation_service.add_message(conversation, sender_type="SYSTEM", content=no_person["response"]) 
                return QueryResponse(**no_person)
            person_name_raw = person_name_raw.strip().strip('?')
            person_names = name_variants(person_name_raw)

        field_aliases = {
            'salary': ['salary', 'annualsalary', 'salaryamount', 'pay', 'basepay', 'base_salary', 'compensation', 'wage', 'earning'],
            'department': ['department', 'dept', 'division', 'team', 'unit'],
            'manager': ['manager', 'managername', 'supervisor', 'boss', 'reporting_manager'],
            'employmentstatus': ['employmentstatus', 'status', 'employment_status', 'work_status'],
            'position': ['position', 'title', 'job_title', 'role', 'designation', 'jobtitle'],
            'location': ['location', 'office', 'site', 'workplace', 'state', 'city'],
        }

        # First pass: find exact name matches
        matching_rows = []
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
            
            # Check if this row matches the requested person
            is_match = False
            if row_name:
                # Check against all name variants
                for variant in person_names:
                    if row_name == norm_name(variant):
                        is_match = True
                        break
            
            if not is_match:
                # Fallback: check if any cell contains the exact name
                person_norms = {norm_name(v) for v in person_names}
                for v in values:
                    if norm_name(str(v)) in person_norms:
                        is_match = True
                        break
            
            if is_match:
                matching_rows.append((i, cand, col_to_val))
        
        # If no exact matches found, return error
        if not matching_rows:
            no_match = {
                "response": f"I couldn't find any records for {person_name_raw}. Please verify the name spelling or check if this person exists in the employee database.",
                "citations": [],
                "confidence": 0.0,
                "requiresHuman": True,
            }
            conversation_service.add_message(conversation, sender_type="SYSTEM", content=no_match["response"])
            return QueryResponse(**no_match)
        
        # Second pass: extract the requested field from matching rows
        best_value = None
        best_row_text = None
        best_score = -1.0
        
        canonical_name_for_memory = None
        for row_idx, row_text, col_to_val in matching_rows:
            # Look for the requested field
            for key in field_aliases.get(requested, [requested]):
                k = norm_col(key)
                if k in col_to_val and str(col_to_val[k]).strip() != '':
                    # Use a simple scoring based on field presence (1.0 for exact match)
                    score = 1.0
                    if score > best_score:
                        best_score = score
                        best_value = str(col_to_val[k]).strip()
                        best_row_text = row_text
                        # Capture a canonical display name from known name columns for memory
                        for nc in ['employee_name', 'name', 'employee', 'empname', 'full_name', 'employee_full_name']:
                            if nc in col_to_val and str(col_to_val[nc]).strip() != '':
                                canonical_name_for_memory = str(col_to_val[nc]).strip()
                    break
        if best_value:
            # Format the response in a human-readable way
            person_display_name = canonical_name_for_memory or person_name_raw
            
            # Format response based on the field type
            if requested == 'salary':
                # Format salary with currency symbol and thousands separator
                try:
                    salary_num = float(best_value.replace(',', '').replace('$', ''))
                    formatted_salary = f"${salary_num:,.0f}"
                    response_text = f"The salary of {person_display_name} is {formatted_salary}."
                except:
                    # Fallback if salary is not a number
                    response_text = f"The salary of {person_display_name} is {best_value}."
            elif requested == 'department':
                response_text = f"The department of {person_display_name} is {best_value}."
            elif requested == 'manager':
                response_text = f"The manager of {person_display_name} is {best_value}."
            elif requested == 'employmentstatus':
                response_text = f"The employment status of {person_display_name} is {best_value}."
            elif requested == 'position':
                response_text = f"{person_display_name} works as a {best_value}."
            elif requested == 'location':
                response_text = f"{person_display_name} is located in {best_value}."
            else:
                # Generic format for other fields
                field_display = requested.replace('_', ' ').title()
                response_text = f"The {field_display.lower()} of {person_display_name} is {best_value}."
            
            response_payload = {
                "response": response_text,
                "citations": [{"source": "row", "title": "Matched record", "relevance": 0.99, "snippet": best_row_text[:160]}],
                "confidence": 0.9,
                "requiresHuman": False,
            }
            # Persist short-term memory of last referenced person
            try:
                convo_ctx['last_person'] = person_display_name
                conversation.context = convo_ctx
                db.add(conversation)
                db.commit()
                db.refresh(conversation)
            except Exception:
                db.rollback()
            conversation_service.add_message(conversation, sender_type="SYSTEM", content=response_payload["response"])            
            return QueryResponse(**response_payload)
        # Avoid falling back to generic RAG when a specific field was requested but not found
        field_display = requested.replace('_', ' ').title()
        no_match = {
            "response": f"I found {person_name_raw} in the database, but their {field_display.lower()} information is not available or empty in the records.",
            "citations": [],
            "confidence": 0.0,
            "requiresHuman": True,
        }
        conversation_service.add_message(conversation, sender_type="SYSTEM", content=no_match["response"])
        return QueryResponse(**no_match)

    # Fallback to generic RAG answer if no structured match
    # Use the previously retrieved candidates and limit to 6 (aligns with sample)
    preselected = candidates[:6] if candidates else []
    result = rag_service.answer(payload.message, preselected_contexts=preselected, tenant_id=str(tenant_uuid), db=db)
    conversation_service.add_message(conversation, sender_type="SYSTEM", content=result["response"])
    return QueryResponse(**result)


