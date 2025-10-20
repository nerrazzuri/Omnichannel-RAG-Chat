"""
Tenant document upload API.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from ai_core.models.knowledge import DocumentUploadRequest, DocumentUploadResponse
from ai_core.services.document_service import DocumentService
from shared.database.session import get_db
from shared.cache.redis import redis_cache

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
    jobId: str = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        # Validate inputs
        if not tenantId:
            raise HTTPException(status_code=400, detail="tenantId is required")
        if not title:
            raise HTTPException(status_code=400, detail="title is required")
        if not file:
            raise HTTPException(status_code=400, detail="file is required")
        
        # Validate tenant ID format
        import uuid
        try:
            uuid.UUID(tenantId)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tenantId format, must be a valid UUID")
        
        # Read file data (FastAPI will stream to memory/disk depending on server config)
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # No hard file size limit enforced here; rely on infrastructure (reverse proxy/app server) limits
        
        # Initialize progress tracking if jobId provided
        if jobId:
            try:
                redis_cache.set_tenant_key(tenantId, f"upload:job:{jobId}", {"phase": "processing", "progress": 0}, ttl=3600)
            except Exception:
                pass

        svc = DocumentService(db)
        name = file.filename.lower() if file.filename else ""
        
        # Process based on file type
        if name.endswith('.csv') or name.endswith('.xlsx'):
            # New pandas-based ingestion for tabular files
            try:
                doc_id, chunk_count = svc.process_pandas_and_store(
                    tenantId, title, file.filename, data, knowledgeBaseId, progress_job_id=jobId
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Tabular ingestion failed: {e}")
        else:
            extracted = svc.extract_text_from_file(file.filename, data)
            if not extracted or not extracted.strip():
                raise HTTPException(status_code=400, detail="No text content could be extracted from the file")
            doc_id, chunk_count = svc.process_and_store(tenantId, title, extracted, knowledgeBaseId, progress_job_id=jobId)
        
        return DocumentUploadResponse(documentId=doc_id, chunkCount=chunk_count, status="INDEXED")
    
    except HTTPException:
        # Re-raise HTTP exceptions with proper JSON formatting
        raise
    except ValueError as e:
        # Handle UUID or other value errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log the actual error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error processing file upload: {str(e)}", exc_info=True)
        
        # Return a generic error message to the client
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )
@router.get("/upload_status")
def upload_status(tenantId: str = Query(...), jobId: str = Query(...)) -> dict:
    try:
        data = redis_cache.get_tenant_key(tenantId, f"upload:job:{jobId}")
        if not isinstance(data, dict):
            return {"jobId": jobId, "phase": "unknown", "progress": 0}
        return {"jobId": jobId, **data}
    except Exception:
        return {"jobId": jobId, "phase": "unknown", "progress": 0}


