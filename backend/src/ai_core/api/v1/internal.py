"""
Internal knowledge API with JWT-based RBAC.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from shared.database.session import get_db
from ai_core.services.internal_knowledge_service import InternalKnowledgeService
from shared.security.jwt import JWTService

router = APIRouter(prefix="/v1/internal", tags=["internal-knowledge"])
jwt_service = JWTService()


def parse_bearer(auth: Optional[str]) -> str:
    if not auth:
        raise HTTPException(status_code=401, detail="Authorization required")
    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return parts[1]


@router.get("/knowledge/list")
def list_knowledge(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    token = parse_bearer(authorization)
    payload = jwt_service.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    role = payload.get("role", "END_USER")
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id missing in token")
    svc = InternalKnowledgeService(db)
    return svc.list_documents(tenant_id=tenant_id, role=role)


@router.post("/knowledge/update")
def update_knowledge(
    body: Dict[str, Any], authorization: Optional[str] = Header(None), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    token = parse_bearer(authorization)
    payload = jwt_service.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    role = payload.get("role", "END_USER")
    doc_id = body.get("id")
    updates = body.get("updates", {})
    if not doc_id:
        raise HTTPException(status_code=400, detail="Missing id")
    svc = InternalKnowledgeService(db)
    try:
        return svc.update_document(role=role, document_id=doc_id, updates=updates)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


