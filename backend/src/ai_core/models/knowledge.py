"""
Pydantic models for knowledge base operations.
"""
from pydantic import BaseModel, Field
from typing import Optional


class DocumentUploadRequest(BaseModel):
    tenant_id: str = Field(..., alias="tenantId")
    title: str
    content: str
    knowledge_base_id: Optional[str] = Field(None, alias="knowledgeBaseId")


class DocumentUploadResponse(BaseModel):
    document_id: str = Field(alias="documentId")
    chunk_count: int = Field(alias="chunkCount")
    status: str


