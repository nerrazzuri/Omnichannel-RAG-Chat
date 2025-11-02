from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from shared.database.session import SessionLocal
from shared.metrics.backup_metrics import backup_metrics
import time


router = APIRouter(prefix="/v1/admin/backup", tags=["admin-backup"])


def get_db():
    s = SessionLocal()
    try:
        yield s
    finally:
        try:
            s.close()
        except Exception:
            pass


def _require_admin(request: Request):
    claims = getattr(request.state, "claims", {}) or {}
    role = (claims.get("role") or "").upper()
    scopes = set((claims.get("scopes") or []))
    if role == "ADMIN" or "backup:write" in scopes:
        return True
    raise HTTPException(status_code=403, detail="forbidden")


class BackupMark(BaseModel):
    system: str  # postgres|redis|qdrant|vault
    status: str  # success|failure
    duration_ms: int | None = None
    size_bytes: int | None = None
    ts_unix: int | None = None


@router.post("/mark")
def mark_backup(payload: BackupMark, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    now = int(payload.ts_unix or time.time())
    ok = payload.status == "success"
    backup_metrics.mark(payload.system, ok, now, payload.duration_ms, payload.size_bytes)
    return {"ok": True}


