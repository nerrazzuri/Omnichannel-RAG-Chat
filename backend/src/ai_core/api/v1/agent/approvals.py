from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from shared.database.session import SessionLocal
from shared.database.models import Approval
from sqlalchemy.orm import Session
from shared.metrics.agent_tool_metrics import agent_tool_metrics


router = APIRouter(prefix="/v1/agent/approvals", tags=["agent-approvals"])


def get_db():
    s = SessionLocal()
    try:
        yield s
    finally:
        try:
            s.close()
        except Exception:
            pass


class ApprovalRequest(BaseModel):
    tenant_id: str
    tool_id: str
    action_payload_hash: str
    requested_by: Optional[str] = None


class ApprovalDecision(BaseModel):
    approval_id: str
    status: str  # approved|denied
    reason: Optional[str] = None
    decided_by: Optional[str] = None


@router.post("/request")
def create_request(req: ApprovalRequest, db: Session = Depends(get_db)):
    rec = Approval(
        tenant_id=req.tenant_id,
        tool_id=req.tool_id,
        action_payload_hash=req.action_payload_hash,
        requested_by=req.requested_by,
        status="pending",
    )
    db.add(rec)
    db.commit()
    agent_tool_metrics.inc_approval_requested(req.tenant_id, req.tool_id)
    return {"approval_id": str(rec.id), "status": rec.status}


@router.post("/decide")
def decide(dec: ApprovalDecision, db: Session = Depends(get_db)):
    rec = db.get(Approval, dec.approval_id)
    if not rec:
        raise HTTPException(status_code=404, detail="approval not found")
    rec.status = "approved" if dec.status == "approved" else "denied"
    rec.reason = dec.reason
    rec.decided_by = dec.decided_by
    from sqlalchemy.sql import func as _func
    rec.decided_at = _func.now()
    db.add(rec)
    db.commit()
    if rec.status == "approved":
        agent_tool_metrics.inc_approval_granted(str(rec.tenant_id), rec.tool_id)
    return {"status": rec.status}


@router.get("/list")
def list_approvals(tenant_id: str = Query(...), status: Optional[str] = Query(None), limit: int = Query(50), db: Session = Depends(get_db)):
    q = db.query(Approval).filter(Approval.tenant_id == tenant_id)
    if status:
        q = q.filter(Approval.status == status)
    q = q.order_by(Approval.created_at.desc()).limit(min(200, max(1, limit)))
    rows = q.all()
    return [{"id": str(r.id), "tool_id": r.tool_id, "status": r.status, "created_at": str(r.created_at), "decided_at": str(r.decided_at) if r.decided_at else None} for r in rows]


