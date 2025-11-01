from __future__ import annotations

import time
import random
import hashlib
from typing import Dict, Any
from sqlalchemy.orm import Session
import logging
from sqlalchemy import and_
from shared.database.session import SessionLocal
from shared.database.models import Approval
from shared.metrics.approval_metrics import approval_metrics
from shared.config.tuning import agent_approval
from ai_core.agents.tools import tool_registry
from ai_core.pipeline.audit_service import write_audit
from shared.security.pii import redact


def _h(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def process_once(db: Session, batch_size: int) -> int:
    rows = (
        db.query(Approval)
        .filter(and_(Approval.status == "approved", Approval.executed == False, Approval.deleted_at == None))  # noqa: E712
        .order_by(Approval.created_at.asc())
        .limit(max(1, int(batch_size)))
        .all()
    )
    approval_metrics.set_queue(len(rows))
    processed = 0
    for rec in rows:
        t0 = time.time()
        try:
            tool = tool_registry.get(rec.tool_id)
            if not tool:
                raise RuntimeError("unknown_tool")
            payload_str = rec.action_payload_json or "{}"
            # naive json parse fallback
            try:
                import json as _json
                payload = _json.loads(payload_str) if payload_str and payload_str.strip().startswith("{") else {}
            except Exception as e:
                logging.getLogger(__name__).exception("[approval_worker.payload_parse] invalid JSON", extra={"approval_id": str(rec.id)})
                payload = {}
            res = tool.execute(tenant_id=str(rec.tenant_id), api_key_id=None, payload=payload)
            out_sum = {k: v for k, v in res.items() if k != "status"}
            out_sum_str = str(out_sum)[:1000]
            rec.executed = True
            rec.executed_at = db.execute("SELECT now()").scalar()  # portable now()
            rec.output_summary = out_sum_str
            rec.output_hash = _h(out_sum_str)
            db.add(rec)
            db.commit()
            approval_metrics.inc_success()
            write_audit(db, str(rec.tenant_id), None, "agent.approval.execute", rec.tool_id, redact(payload_str), redact(out_sum_str), True, int((time.time()-t0)*1000), category="agent")
            approval_metrics.observe_latency_ms(int((time.time()-t0)*1000))
            processed += 1
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            approval_metrics.inc_failure()
            approval_metrics.observe_latency_ms(int((time.time()-t0)*1000))
            logging.getLogger(__name__).exception("[approval_worker.process] execution error", extra={"approval_id": str(rec.id), "tool": rec.tool_id})
            # simple retry jitter handled by outer loop cadence
            continue
    return processed


def loop(stop_flag: Dict[str, bool]) -> None:
    while not stop_flag.get("stop"):
        s = SessionLocal()
        try:
            _ = process_once(s, agent_approval.batch_size)
        finally:
            try:
                s.close()
            except Exception:
                pass
        time.sleep(max(1, int(agent_approval.poll_interval_s)))


