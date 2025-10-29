from __future__ import annotations

import hashlib
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from shared.database.models import AuditLog


def _h(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def write_audit(
    db: Session,
    tenant_id: str,
    user_id: Optional[str],
    action: str,
    resource: str,
    request_text: str,
    response_text: str,
    success: bool,
    latency_ms: int,
    model: Optional[str] = None,
    token_input: Optional[int] = None,
    token_output: Optional[int] = None,
    category: Optional[str] = None,
    auth_type: Optional[str] = None,
    api_key_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    classification: Optional[str] = None,
    origin: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Enqueue audit entry; fall back to direct write if queue unavailable."""
    try:
        from shared.queue.retry_queue import retry_queue
        payload = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "request_hash": _h(request_text),
            "response_hash": _h(response_text),
            "success": success,
            "latency_ms": latency_ms,
            "model": model,
            "token_input": token_input,
            "token_output": token_output,
            "category": category,
            "auth_type": auth_type,
            "api_key_id": api_key_id,
            "correlation_id": correlation_id,
            "classification": classification,
            "origin": origin,
            "extra": extra or {},
        }
        retry_queue.enqueue("audit_log", tenant_id, payload)
        return
    except Exception:
        pass

    try:
        rec = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            api_key_id=api_key_id,
            correlation_id=correlation_id,
            auth_type=auth_type,
            category=category,
            action=action,
            resource=resource,
            classification=classification,
            origin=origin,
            request_hash=_h(request_text),
            response_hash=_h(response_text),
            success=success,
            latency_ms=latency_ms,
            model=model,
            token_input=token_input,
            token_output=token_output,
            extra=extra or {},
        )
        db.add(rec)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


