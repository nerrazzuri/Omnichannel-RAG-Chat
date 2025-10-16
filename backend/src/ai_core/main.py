"""
FastAPI application for AI Core - RAG-powered conversational AI service.
"""
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import os
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from ai_core.api.v1.query import router as query_router
from ai_core.api.webhooks.whatsapp import router as whatsapp_router
from ai_core.api.webhooks.teams import router as teams_router
from ai_core.api.webhooks.telegram import router as telegram_router
from ai_core.api.v1.internal import router as internal_router
from ai_core.api.v1.tenant import router as tenant_router
from shared.database.session import create_tables, SessionLocal
from shared.database.models import Tenant
import uuid

# Configure structured logging
class ColorFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\x1b[36m',      # Cyan
        'INFO': '\x1b[32m',       # Green
        'WARNING': '\x1b[33m',    # Yellow
        'ERROR': '\x1b[31m',      # Red
        'CRITICAL': '\x1b[41m',   # Red background
    }
    RESET = '\x1b[0m'

    def format(self, record: logging.LogRecord) -> str:
        level_color = self.COLORS.get(record.levelname, '')
        msg = super().format(record)
        if level_color:
            return f"{level_color}{msg}{self.RESET}"
        return msg

handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
handler.setFormatter(ColorFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers = [handler]
app_logger = logging.getLogger(__name__)

REQUEST_COUNT = Counter('ai_core_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('ai_core_request_latency_seconds', 'Request latency', ['endpoint'])

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    app_logger.info("Starting AI Core service...")
    # Initialize database tables (dev/test SQLite); in production use Alembic
    try:
        create_tables()
    except Exception as e:
        app_logger.warning(f"DB initialization skipped/failed: {e}")
    # Seed default tenant for development/staging to avoid FK violations
    try:
        default_tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        db = SessionLocal()
        try:
            existing = db.get(Tenant, default_tenant_id)
            if not existing:
                tenant = Tenant(
                    id=default_tenant_id,
                    name="Global Tenant",
                    domain="global",
                    subscription_tier="BASIC",
                    settings={},
                )
                db.add(tenant)
                db.commit()
        finally:
            db.close()
    except Exception as e:
        app_logger.warning(f"Default tenant seeding failed or skipped: {e}")
    yield
    app_logger.info("Shutting down AI Core service...")
    # Cleanup logic here

# Create FastAPI application
app = FastAPI(
    title="Omnichannel RAG Chatbot - AI Core",
    description="Enterprise-grade RAG-powered conversational AI service",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler to ensure JSON responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )

@app.get("/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ai_core",
        "version": "1.0.0",
        "timestamp": "2025-01-01T00:00:00Z"
    }

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

app.include_router(query_router)
app.include_router(whatsapp_router)
app.include_router(internal_router)
app.include_router(teams_router)
app.include_router(telegram_router)
app.include_router(tenant_router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
