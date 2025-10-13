"""
Tenant document upload API.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from ai_core.models.knowledge import DocumentUploadRequest, DocumentUploadResponse
from ai_core.services.document_service import DocumentService
from shared.database.session import get_db

router = APIRouter(prefix="/v1/tenant", tags=["tenant"])


@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document(body: DocumentUploadRequest, db: Session = Depends(get_db)) -> DocumentUploadResponse:
    if not body.tenant_id or not body.title or not body.content:
        raise HTTPException(status_code=400, detail="Missing tenantId, title or content")
    kb_id = body.knowledge_base_id or "00000000-0000-0000-0000-000000000000"
    svc = DocumentService(db)
    doc_id, chunk_count = svc.process_and_store(body.tenant_id, body.title, body.content, kb_id)
    return DocumentUploadResponse(documentId=doc_id, chunkCount=chunk_count, status="INDEXED")


@router.post("/upload_file", response_model=DocumentUploadResponse)
async def upload_document_file(
    tenantId: str = Form(...),
    title: str = Form(...),
    knowledgeBaseId: str = Form("00000000-0000-0000-0000-000000000000"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    data = await file.read()
    svc = DocumentService(db)
    name = file.filename.lower()
    if name.endswith('.csv') or name.endswith('.xlsx'):
        rows = svc.extract_rows_from_file(file.filename, data)
        doc_id, chunk_count = svc.process_rows_and_store(tenantId, title, rows, knowledgeBaseId)
    else:
        extracted = svc.extract_text_from_file(file.filename, data)
        doc_id, chunk_count = svc.process_and_store(tenantId, title, extracted, knowledgeBaseId)
    return DocumentUploadResponse(documentId=doc_id, chunkCount=chunk_count, status="INDEXED")


