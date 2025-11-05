from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from shared.database.session import SessionLocal
from ai_core.services.tenant_manager import TenantManager
from ai_core.api.v1.admin.tenants import _require_admin  # reuse admin guard


router = APIRouter(prefix="/v1/admin/tenants", tags=["admin-tenant-manager"])


def get_db():
    s = SessionLocal()
    try:
        yield s
    finally:
        try:
            s.close()
        except Exception:
            pass


class CreateBody(BaseModel):
    name: str
    plan_type: str
    domain: str


@router.post("")
def create(body: CreateBody, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    tm = TenantManager(db)
    return tm.create(body.name, body.domain, body.plan_type)


@router.post("/{tenant_id}/activate")
def activate(tenant_id: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    tm = TenantManager(db)
    return tm.activate(tenant_id)


class PlanBody(BaseModel):
    target_plan: str


@router.post("/{tenant_id}/upgrade")
def upgrade(tenant_id: str, body: PlanBody, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    tm = TenantManager(db)
    return tm.upgrade(tenant_id, body.target_plan)


@router.post("/{tenant_id}/downgrade")
def downgrade(tenant_id: str, body: PlanBody, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    tm = TenantManager(db)
    return tm.downgrade(tenant_id, body.target_plan)


@router.post("/{tenant_id}/suspend")
def suspend(tenant_id: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    tm = TenantManager(db)
    return tm.suspend(tenant_id)


@router.post("/{tenant_id}/resume")
def resume(tenant_id: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    tm = TenantManager(db)
    return tm.resume(tenant_id)


@router.delete("/{tenant_id}")
def delete(tenant_id: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    tm = TenantManager(db)
    return tm.delete(tenant_id)


@router.get("/{tenant_id}/dry-run")
def dry_run(tenant_id: str, target_plan: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    tm = TenantManager(db)
    return tm.dry_run(tenant_id, target_plan)


