"""API endpoints for reranker management."""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel
 
from ...services.reranker_service import get_reranker, create_reranker
from ...services.rag_service import RAGService
 
router = APIRouter(prefix="/reranker", tags=["reranker"])
 
class RerankRequest(BaseModel):
    query: str
    documents: List[str]
    top_k: int = 10
 
class RerankResponse(BaseModel):
    documents: List[str]
    scores: List[float]
    processing_time: float
    method_used: str
 
@router.post("/rerank", response_model=RerankResponse)
async def rerank_documents(
    request: RerankRequest,
):
    """Rerank documents using the advanced reranker."""
    try:
        reranker = get_reranker()
        result = reranker.multi_stage_reranking(
            query=request.query,
            documents=request.documents,
            top_k=request.top_k
        )
        
        return RerankResponse(
            documents=result.documents,
            scores=result.scores,
            processing_time=result.processing_time,
            method_used=result.method_used
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@router.get("/status")
async def get_reranker_status():
    """Get reranker status and configuration."""
    try:
        # 从RAGService获取状态
        rag_service = RAGService()
        return rag_service.get_reranker_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@router.post("/toggle")
async def toggle_reranker(
    enabled: bool,
):
    """Toggle reranker on/off."""
    try:
        rag_service = RAGService()
        result = rag_service.toggle_reranker(enabled)
        return {"enabled": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@router.post("/clear-cache")
async def clear_reranker_cache():
    """Clear reranker caches."""
    try:
        reranker = get_reranker()
        reranker.clear_cache()
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))