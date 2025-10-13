# Implementation Details: Omnichannel Enterprise RAG Chatbot Platform

## Overview

This document provides concrete implementation guidance, code examples, and step-by-step procedures for executing the tasks defined in `tasks.md`. Each section corresponds to major implementation areas with specific technical details.

## 1. Database Setup Sequence

### 1.1 PostgreSQL Multi-Tenant Schema Setup

**Step 1: Create tenant-separated schemas**
```sql
-- Create base schemas
CREATE SCHEMA tenant_template;
CREATE SCHEMA public;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

**Step 2: Create tenant management functions**
```sql
-- Function to create new tenant schema
CREATE OR REPLACE FUNCTION create_tenant_schema(tenant_domain TEXT)
RETURNS TEXT AS $$
DECLARE
    schema_name TEXT := 'tenant_' || tenant_domain;
BEGIN
    EXECUTE format('CREATE SCHEMA %I', schema_name);

    -- Create tables in new schema
    EXECUTE format('
        CREATE TABLE %I.tenants (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(255) NOT NULL,
            domain VARCHAR(255) UNIQUE NOT NULL,
            subscription_tier VARCHAR(50) DEFAULT ''BASIC'',
            settings JSONB DEFAULT ''{}'',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE %I.users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL,
            external_id VARCHAR(255),
            user_type VARCHAR(50) NOT NULL,
            role VARCHAR(50) DEFAULT ''END_USER'',
            preferences JSONB DEFAULT ''{}'',
            last_active_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (tenant_id) REFERENCES %I.tenants(id) ON DELETE CASCADE
        );

        CREATE TABLE %I.conversations (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            channel VARCHAR(50) NOT NULL,
            status VARCHAR(50) DEFAULT ''ACTIVE'',
            context JSONB DEFAULT ''{}'',
            started_at TIMESTAMP DEFAULT NOW(),
            last_message_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES %I.tenants(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES %I.users(id) ON DELETE CASCADE
        );

        CREATE TABLE %I.messages (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            conversation_id UUID NOT NULL,
            sender_type VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            message_type VARCHAR(50) DEFAULT ''TEXT'',
            metadata JSONB DEFAULT ''{}'',
            timestamp TIMESTAMP DEFAULT NOW(),
            is_processed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (conversation_id) REFERENCES %I.conversations(id) ON DELETE CASCADE
        );
    ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);

    RETURN schema_name;
END;
$$ LANGUAGE plpgsql;

-- Function to get current tenant context
CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS UUID AS $$
BEGIN
    RETURN current_setting('app.current_tenant_id', TRUE)::UUID;
END;
$$ LANGUAGE plpgsql;
```

**Step 3: Set up Row Level Security (RLS)**
```sql
-- Enable RLS on all tenant tables
ALTER TABLE tenant_template.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_template.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_template.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_template.messages ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY tenant_isolation ON tenant_template.tenants
    FOR ALL USING (id = get_current_tenant_id());

CREATE POLICY user_tenant_isolation ON tenant_template.users
    FOR ALL USING (tenant_id = get_current_tenant_id());

CREATE POLICY conversation_tenant_isolation ON tenant_template.conversations
    FOR ALL USING (tenant_id = get_current_tenant_id());

CREATE POLICY message_tenant_isolation ON tenant_template.messages
    FOR ALL USING (
        conversation_id IN (
            SELECT id FROM tenant_template.conversations
            WHERE tenant_id = get_current_tenant_id()
        )
    );
```

### 1.2 Alembic Migration Setup

**alembic/env.py**
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.database.session import Base

config = context.config

fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

**alembic/versions/initial_schema.py**
```python
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create tenant template schema
    op.execute("CREATE SCHEMA IF NOT EXISTS tenant_template")

    # Create base tables in tenant_template
    op.create_table('tenants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('subscription_tier', sa.String(50), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='tenant_template'
    )

    op.create_index('ix_tenant_template_tenants_domain', 'tenants', ['domain'], unique=True, schema='tenant_template')

def downgrade():
    op.drop_table('tenants', schema='tenant_template')
    op.execute("DROP SCHEMA IF EXISTS tenant_template CASCADE")
```

## 2. Authentication Implementation

### 2.1 JWT Token Service

**backend/src/shared/security/jwt.py**
```python
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from jwt.exceptions import InvalidTokenError
import os

class JWTService:
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET", "your-secret-key")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60

    def create_access_token(self, data: Dict[str, Any], tenant_id: str) -> str:
        to_encode = data.copy()
        to_encode.update({
            "tenant_id": tenant_id,
            "exp": datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
            "iat": datetime.utcnow(),
            "type": "access"
        })

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != "access":
                return None
            return payload
        except InvalidTokenError:
            return None

    def get_tenant_id_from_token(self, token: str) -> Optional[str]:
        payload = self.verify_token(token)
        return payload.get("tenant_id") if payload else None
```

### 2.2 Dual Authentication Strategy

**Internal Staff (SAML/OAuth)**
```python
# backend/src/gateway/middleware/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import requests
from typing import Optional

class SAMLAuth:
    def __init__(self):
        self.saml_config = {
            "entity_id": os.getenv("SAML_ENTITY_ID"),
            "sso_url": os.getenv("SAML_SSO_URL"),
            "certificate": os.getenv("SAML_CERTIFICATE")
        }

    async def authenticate_saml(self, saml_response: str) -> Dict[str, Any]:
        # Parse SAML response and extract user info
        # Validate against identity provider
        # Return user data with tenant context
        pass

class InternalAuthMiddleware:
    def __init__(self):
        self.jwt_service = JWTService()
        self.saml_auth = SAMLAuth()

    async def authenticate_internal_user(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
    ) -> Dict[str, Any]:
        token = credentials.credentials

        # Try JWT first
        payload = self.jwt_service.verify_token(token)
        if payload and payload.get("user_type") == "INTERNAL_STAFF":
            return payload

        # If JWT fails, check for SAML token in custom header
        # Implementation depends on SAML provider (Auth0, Okta, etc.)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication for internal user"
        )
```

**External Customers (Social Login)**
```python
# backend/src/gateway/middleware/auth.py (continued)
class SocialAuth:
    def __init__(self):
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.facebook_app_id = os.getenv("FACEBOOK_APP_ID")

    async def authenticate_google(self, token: str) -> Dict[str, Any]:
        # Verify Google OAuth token
        response = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
        if response.status_code == 200:
            user_info = response.json()
            return {
                "user_id": user_info["sub"],
                "email": user_info["email"],
                "user_type": "EXTERNAL_CUSTOMER",
                "verified": user_info["email_verified"]
            }
        raise HTTPException(status_code=401, detail="Invalid Google token")

    async def authenticate_facebook(self, token: str) -> Dict[str, Any]:
        # Verify Facebook OAuth token
        # Similar implementation for Facebook
        pass

class ExternalAuthMiddleware:
    def __init__(self):
        self.social_auth = SocialAuth()
        self.jwt_service = JWTService()

    async def authenticate_external_user(
        self,
        authorization: Optional[str] = Header(None)
    ) -> Dict[str, Any]:
        if not authorization:
            return None  # Anonymous access allowed for external users

        try:
            scheme, token = authorization.split()
            if scheme.lower() == "bearer":
                payload = self.jwt_service.verify_token(token)
                if payload and payload.get("user_type") == "EXTERNAL_CUSTOMER":
                    return payload
            elif scheme.lower() == "google":
                return await self.social_auth.authenticate_google(token)
            elif scheme.lower() == "facebook":
                return await self.social_auth.authenticate_facebook(token)

        except Exception:
            pass

        return None  # Anonymous fallback
```

## 3. RAG Pipeline Implementation

### 3.1 Document Processing and Chunking

**backend/src/ai_core/services/document_service.py**
```python
import re
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
import os

class DocumentProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=700,  # From spec.md RAG Configuration
            chunk_overlap=100,  # From spec.md RAG Configuration
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",  # From spec.md
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

    async def process_document(self, file_path: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Extract text from document (PDF, DOCX, TXT)
        text_content = await self.extract_text(file_path)

        # Split into chunks
        chunks = self.text_splitter.split_text(text_content)

        # Generate embeddings for each chunk
        chunk_objects = []
        for i, chunk in enumerate(chunks):
            embedding = await self.embeddings.aembed_query(chunk)

            chunk_objects.append({
                "content": chunk,
                "chunk_index": i,
                "embedding": embedding,
                "metadata": {
                    **metadata,
                    "chunk_size": len(chunk),
                    "total_chunks": len(chunks)
                }
            })

        return chunk_objects

    async def extract_text(self, file_path: str) -> str:
        # Implementation depends on file type
        # Use libraries like PyPDF2, python-docx, etc.
        pass
```

### 3.2 Hybrid Retrieval Implementation

**backend/src/ai_core/services/rag_service.py**
```python
from typing import List, Dict, Any, Optional
from langchain.vectorstores import Qdrant
from langchain.retrievers import BM25Retriever, EnsembleRetriever
from langchain.schema import Document
import numpy as np

class HybridRetriever:
    def __init__(self, vector_store: Qdrant, bm25_retriever: BM25Retriever):
        self.vector_store = vector_store
        self.bm25_retriever = bm25_retriever
        self.ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, vector_store.as_retriever()],
            weights=[0.3, 0.7]  # Favor semantic search
        )

    async def retrieve(self, query: str, top_k: int = 5) -> List[Document]:
        # Get results from both retrievers
        bm25_docs = await self.bm25_retriever.aget_relevant_documents(query)
        vector_docs = await self.vector_store.as_retriever().aget_relevant_documents(query)

        # Apply Reciprocal Rank Fusion (RRF)
        fused_docs = self.reciprocal_rank_fusion([bm25_docs, vector_docs], k=top_k)

        return fused_docs

    def reciprocal_rank_fusion(self, doc_lists: List[List[Document]], k: int = 5) -> List[Document]:
        # RRF implementation
        doc_scores = {}

        for doc_list in doc_lists:
            for rank, doc in enumerate(doc_list, 1):
                doc_id = doc.metadata.get("source", str(doc))
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {"doc": doc, "score": 0}
                doc_scores[doc_id]["score"] += 1 / (rank + 60)  # RRF constant

        # Sort by RRF score and return top k
        sorted_docs = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
        return [item["doc"] for item in sorted_docs[:k]]

class RAGService:
    def __init__(self, hybrid_retriever: HybridRetriever):
        self.retriever = hybrid_retriever

    async def generate_response(
        self,
        query: str,
        conversation_history: List[Dict[str, Any]],
        tenant_id: str
    ) -> Dict[str, Any]:
        # Retrieve relevant context
        context_docs = await self.retriever.retrieve(query)

        # Build prompt with context
        context_text = "\n".join([doc.page_content for doc in context_docs])

        # Generate response using LangChain/OpenAI
        # Implementation depends on chosen LLM provider

        return {
            "response": generated_response,
            "citations": [
                {
                    "source": doc.metadata.get("source", "unknown"),
                    "title": doc.metadata.get("title", "Document"),
                    "relevance": 0.8  # Calculate based on similarity score
                }
                for doc in context_docs
            ],
            "confidence": calculate_confidence_score,
            "context_docs": len(context_docs)
        }
```

## 4. Channel Integration Examples

### 4.1 WhatsApp Webhook Handler

**backend/src/ai_core/api/webhooks/whatsapp.py**
```python
from fastapi import APIRouter, Request, HTTPException, Header
import hmac
import hashlib
import json
from typing import Dict, Any

router = APIRouter()

@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None)
):
    # Verify webhook signature
    body = await request.body()
    expected_signature = hmac.new(
        os.getenv("WHATSAPP_WEBHOOK_SECRET").encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(f"sha256={expected_signature}", x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse WhatsApp webhook payload
    payload = await request.json()

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "messages":
                message_data = change["value"]

                # Extract message info
                message = message_data.get("messages", [{}])[0]
                if not message:
                    continue

                # Normalize message format
                normalized_message = {
                    "platform": "whatsapp",
                    "message_id": message.get("id"),
                    "from_user": message.get("from"),
                    "timestamp": message.get("timestamp"),
                    "content": message.get("text", {}).get("body", ""),
                    "message_type": "text"
                }

                # Route to conversation service
                await conversation_service.process_message(normalized_message)

    return {"status": "ok"}
```

### 4.2 Message Normalization

**backend/src/shared/utils/message_utils.py**
```python
from typing import Dict, Any, Optional
from datetime import datetime

class MessageNormalizer:
    @staticmethod
    def normalize_whatsapp_message(whatsapp_payload: Dict[str, Any]) -> Dict[str, Any]:
        message = whatsapp_payload.get("messages", [{}])[0]

        return {
            "platform": "whatsapp",
            "platform_message_id": message.get("id"),
            "sender_id": message.get("from"),
            "recipient_id": message.get("to"),
            "timestamp": datetime.fromtimestamp(int(message.get("timestamp", 0))),
            "content": message.get("text", {}).get("body", ""),
            "message_type": MessageNormalizer._get_whatsapp_message_type(message),
            "metadata": {
                "display_phone_number": whatsapp_payload.get("display_phone_number"),
                "phone_number_id": whatsapp_payload.get("phone_number_id")
            }
        }

    @staticmethod
    def normalize_teams_message(teams_payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "platform": "teams",
            "platform_message_id": teams_payload.get("id"),
            "sender_id": teams_payload.get("from", {}).get("id"),
            "channel_id": teams_payload.get("channelId"),
            "timestamp": datetime.fromisoformat(teams_payload.get("timestamp").replace('Z', '+00:00')),
            "content": teams_payload.get("text", ""),
            "message_type": "text",
            "metadata": {
                "conversation_id": teams_payload.get("conversation", {}).get("id"),
                "service_url": teams_payload.get("serviceUrl")
            }
        }

    @staticmethod
    def _get_whatsapp_message_type(message: Dict[str, Any]) -> str:
        if "text" in message:
            return "text"
        elif "image" in message:
            return "image"
        elif "document" in message:
            return "document"
        elif "location" in message:
            return "location"
        else:
            return "unknown"
```

## 5. API Endpoint Implementations

### 5.1 Query Endpoint

**backend/src/ai_core/api/v1/query.py**
```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    user_id: Optional[str] = Field(None, description="User identifier")
    message: str = Field(..., min_length=1, max_length=4000, description="User's message or query")
    channel: str = Field(..., description="Communication channel")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")

class QueryResponse(BaseModel):
    response: str
    citations: List[Dict[str, Any]]
    confidence: float
    requires_human: bool
    conversation_id: Optional[str] = None

@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> QueryResponse:
    """
    Process conversational query with RAG-powered response generation.
    Reference: See contracts/openapi.yaml for complete API specification
    """
    try:
        # Validate tenant access
        if current_user.get("tenant_id") != request.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )

        # Get or create conversation context
        conversation_id = request.context.get("conversation_id") if request.context else None

        # Process query through RAG service
        result = await rag_service.generate_response(
            query=request.message,
            conversation_history=[],  # Load from database
            tenant_id=request.tenant_id
        )

        # Format response according to API contract
        return QueryResponse(
            response=result["response"],
            citations=result["citations"],
            confidence=result["confidence"],
            requires_human=result["confidence"] < 0.5,  # From spec.md confidence thresholds
            conversation_id=conversation_id
        )

    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process query"
        )
```

## 6. Environment Configuration

### 6.1 Application Configuration

**backend/src/shared/config/settings.py**
```python
from pydantic import BaseSettings
import os

class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/chatbot_dev")

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # AI Services
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    azure_openai_endpoint: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_openai_key: Optional[str] = os.getenv("AZURE_OPENAI_KEY")

    # Authentication
    jwt_secret: str = os.getenv("JWT_SECRET", "change-this-secret")
    jwt_expires_minutes: int = int(os.getenv("JWT_EXPIRES_MINUTES", "60"))

    # External Services
    whatsapp_verify_token: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    whatsapp_access_token: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")

    # Monitoring
    sentry_dsn: Optional[str] = os.getenv("SENTRY_DSN")

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

## 7. Testing Implementation Examples

### 7.1 Contract Tests

**backend/tests/contract/test_query_contract.py**
```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_query_endpoint_contract():
    """Test that /v1/query endpoint matches OpenAPI specification"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test request matching QueryRequest schema
        response = await client.post(
            "/v1/query",
            json={
                "tenant_id": "test-tenant-id",
                "message": "What are your business hours?",
                "channel": "web"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        # Should return 200 with QueryResponse structure
        assert response.status_code == 200
        data = response.json()

        # Validate response structure matches contract
        assert "response" in data
        assert "citations" in data
        assert "confidence" in data
        assert "requires_human" in data
        assert isinstance(data["citations"], list)
        assert 0 <= data["confidence"] <= 1
```

### 7.2 Integration Tests

**backend/tests/integration/test_whatsapp_flow.py**
```python
import pytest
from unittest.mock import AsyncMock, patch
from app.api.webhooks.whatsapp import whatsapp_webhook

@pytest.mark.asyncio
async def test_whatsapp_message_processing():
    """Test complete WhatsApp message processing flow"""
    # Mock WhatsApp webhook payload
    mock_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "test_entry",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": "test_phone"},
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": "123456789"}],
                    "messages": [{
                        "from": "123456789",
                        "id": "test_message_id",
                        "timestamp": "1675620000",
                        "type": "text",
                        "text": {"body": "Hello, I need help"}
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    # Mock conversation service
    with patch("app.api.webhooks.whatsapp.conversation_service") as mock_conv_service:
        mock_conv_service.process_message = AsyncMock()

        # Call webhook handler
        response = await whatsapp_webhook(mock_payload)

        # Verify response
        assert response == {"status": "ok"}

        # Verify message was processed
        mock_conv_service.process_message.assert_called_once()
        call_args = mock_conv_service.process_message.call_args[0][0]

        # Verify message normalization
        assert call_args["platform"] == "whatsapp"
        assert call_args["content"] == "Hello, I need help"
        assert call_args["sender_id"] == "123456789"
```

## 8. Deployment Configuration

### 8.1 Docker Compose for Local Development

**infrastructure/docker-compose.dev.yml**
```yaml
version: '3.8'
services:
  postgresql:
    image: postgres:15
    environment:
      POSTGRES_DB: chatbot_dev
      POSTGRES_USER: chatbot_user
      POSTGRES_PASSWORD: chatbot_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  qdrant:
    image: qdrant/qdrant:v1.5.0
    ports:
      - "6333:6333"
    volumes:
      - qdrant_storage:/qdrant/storage

volumes:
  postgres_data:
  redis_data:
  qdrant_storage:
```

### 8.2 Kubernetes Deployment

**infrastructure/kubernetes/base/backend-deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chatbot-backend
  labels:
    app: chatbot-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: chatbot-backend
  template:
    metadata:
      labels:
        app: chatbot-backend
    spec:
      containers:
      - name: chatbot-backend
        image: chatbot-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: chatbot-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: chatbot-secrets
              key: redis-url
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: chatbot-secrets
              key: jwt-secret
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /v1/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## 9. Monitoring and Observability

### 9.1 Structured Logging

**backend/src/shared/utils/logging.py**
```python
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

class StructuredLogger:
    def __init__(self, logger_name: str):
        self.logger = logging.getLogger(logger_name)

    def log_conversation_event(
        self,
        event_type: str,
        conversation_id: str,
        user_id: str,
        tenant_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "correlation_id": str(uuid.uuid4()),
            "metadata": metadata or {}
        }

        self.logger.info(json.dumps(log_entry))

    def log_rag_query(
        self,
        query: str,
        response_confidence: float,
        context_docs_count: int,
        tenant_id: str
    ):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "rag_query",
            "query_length": len(query),
            "response_confidence": response_confidence,
            "context_docs_count": context_docs_count,
            "tenant_id": tenant_id,
            "correlation_id": str(uuid.uuid4())
        }

        self.logger.info(json.dumps(log_entry))
```

This implementation details document provides concrete code examples and step-by-step procedures for all major components. Use this as a reference when implementing the tasks in `tasks.md`.
