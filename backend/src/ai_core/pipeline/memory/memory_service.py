from __future__ import annotations

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import uuid
import re

from shared.database.models import ConversationMemory
from shared.config.tuning import memory as mem_cfg
from shared.metrics.memory_metrics import memory_metrics
from ai_core.pipeline.llm.llm_client import LLMClient


_PII_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PII_PHONE = re.compile(r"\b(?:\+?\d[\s-]?){7,14}\b")


def _redact_pii(text: str) -> str:
    s = _PII_EMAIL.sub("[REDACTED_EMAIL]", text or "")
    s = _PII_PHONE.sub("[REDACTED_PHONE]", s)
    return s


class MemoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._llm = LLMClient()

    def append_turn(self, tenant_id: str, session_id: str, role: str, content: str) -> None:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(days=mem_cfg.ttl_days)
        safe = _redact_pii(content or "")
        rec = ConversationMemory(
            tenant_id=uuid.UUID(str(tenant_id)),
            session_id=uuid.UUID(str(session_id)),
            role=str(role),
            content=safe,
            created_at=now,
            expires_at=exp,
        )
        self.db.add(rec)
        self.db.commit()
        try:
            memory_metrics.inc_entries(tenant_id)
        except Exception:
            pass

    def _summarize(self, history_text: str) -> str:
        prompt = (
            "Summarize the prior conversation between the user and the assistant in concise bullet form.\n"
            "Keep facts, decisions, and unresolved questions.\n"
            "Do not repeat greetings or small talk.\n"
            "Use 3-7 bullets."
        )
        out = self._llm.generate(query=prompt, contexts=[history_text], intent="summary", result_hint=None)
        return out.get("text", "").strip()

    def get_context(self, tenant_id: str, session_id: str, limit_recent: int = 5) -> Dict[str, Any]:
        q = (
            self.db.query(ConversationMemory)
            .filter(ConversationMemory.tenant_id == uuid.UUID(str(tenant_id)))
            .filter(ConversationMemory.session_id == uuid.UUID(str(session_id)))
            .order_by(ConversationMemory.created_at.asc())
        )
        rows: List[ConversationMemory] = list(q.all())
        if not rows:
            return {"recent_turns": [], "summary": None}
        # Summarize if needed
        summary: Optional[str] = None
        if len(rows) > mem_cfg.summary_trigger_turns:
            older = rows[:-limit_recent]
            history_text = "\n".join([f"{r.role}: {r.content}" for r in older])
            try:
                summary = self._summarize(history_text)
                memory_metrics.inc_summary_ops(tenant_id)
                # Store or update a summary record (role='assistant' with summary field)
                now = datetime.now(timezone.utc)
                exp = now + timedelta(days=mem_cfg.ttl_days)
                sum_rec = ConversationMemory(
                    tenant_id=uuid.UUID(str(tenant_id)),
                    session_id=uuid.UUID(str(session_id)),
                    role="assistant",
                    content="",
                    summary=summary,
                    created_at=now,
                    expires_at=exp,
                )
                self.db.add(sum_rec)
                self.db.commit()
            except Exception:
                summary = None
        recent = rows[-limit_recent:]
        recent_turns = [f"{r.role}: {r.content}" for r in recent]
        return {"recent_turns": recent_turns, "summary": summary}


