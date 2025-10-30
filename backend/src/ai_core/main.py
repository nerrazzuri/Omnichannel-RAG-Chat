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
from .api.v1.reranker import router as reranker_router
from ai_core.api.v1.admin.api_keys import router as apikey_router
from ai_core.api.v1.admin.rerank import router as rerank_admin_router
from ai_core.api.v1.feedback import router as feedback_router
from shared.database.session import create_tables, SessionLocal
from shared.database.models import Tenant
import uuid
import threading
import time

from shared.vector.qdrant import qdrant_service
from shared.queue.retry_queue import retry_queue
from ai_core.pipeline.embedding.embedding_service import EmbeddingService
from shared.metrics.reliability_metrics import reliability_metrics
from shared.config.tuning import qdrant_recovery
from shared.metrics.cost_aggregator import rolling_cost
from shared.config.tuning import cost as cost_cfg
from shared.config.tuning import connectors as connectors_cfg
from shared.metrics.stability_metrics import stability_metrics
from shared.utils.log_and_continue import log_and_continue

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

# Correlation ID middleware
from starlette.middleware.base import BaseHTTPMiddleware
import uuid as _uuid
from ai_core.api.middleware.access import AccessControlMiddleware

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        corr_id = request.headers.get("X-Correlation-ID") or str(_uuid.uuid4())
        # attach to request state
        request.state.correlation_id = corr_id
        # add to logs
        logging.LoggerAdapter(logger, {"correlation_id": corr_id})
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response

REQUEST_COUNT = Counter('ai_core_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('ai_core_request_latency_seconds', 'Request latency', ['endpoint'])

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    app_logger.info("Starting AI Core service...")
    # Startup validations and uptime start
    global _START_TS
    _START_TS = __import__('time').time()
    try:
        _validate_startup()
    except Exception as e:
        app_logger.error(f"Startup validation failed: {e}")
        raise
    # Initialize schema: create tables in dev; Alembic upgrade in non-dev
    try:
        env = os.getenv("ENV", "dev").lower()
        if env in ("dev", "local", "test"):
            create_tables()
        else:
            try:
                from alembic.config import Config as _AlConfig
                from alembic import command as _alcmd
                import pathlib as _pl
                base = _pl.Path(__file__).resolve().parents[3]  # backend/
                cfg = _AlConfig(str(base / "alembic.ini"))
                _alcmd.upgrade(cfg, "head")
            except Exception as _e:
                app_logger.error(f"Alembic upgrade failed: {_e}")
                raise
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

    # Background: Qdrant health monitor and retry worker
    stop_flag = {"stop": False}

    def _qdrant_health_loop():
        app_logger.info("qdrant health loop started", extra={"module_name": "qdrant_health", "pid": os.getpid()})
        last_ok = time.time()
        while not stop_flag["stop"]:
            try:
                ok = qdrant_service.ping()
                if ok:
                    last_ok = time.time()
                else:
                    stability_metrics.inc_bg_failure("qdrant_health")
            except Exception as e:
                stability_metrics.inc_bg_failure("qdrant_health")
                stability_metrics.inc_bg_retry("qdrant_health")
                log_and_continue(e, "qdrant.health", None, None)
            time.sleep(max(0.1, qdrant_recovery.health_interval_ms / 1000.0))

    def _retry_worker_loop():
        app_logger.info("retry worker loop started", extra={"module_name": "retry_worker", "pid": os.getpid()})
        emb = EmbeddingService()
        while not stop_flag["stop"]:
            # process embedding jobs
            job = retry_queue.dequeue("embed_query", timeout=1)
            if job:
                try:
                    tenant_id = str(job.get("tenant_id") or "global")
                    payload = job.get("payload") or {}
                    q = str(payload.get("query") or "")
                    if q:
                        _ = emb.embed_query(q, tenant_id)
                except Exception as e:
                    stability_metrics.inc_bg_failure("retry_worker")
                    stability_metrics.inc_bg_retry("retry_worker")
                    log_and_continue(e, "retry_worker.embed", tenant_id, None)
                continue
            # process qdrant upsert jobs
            job2 = retry_queue.dequeue("qdrant_upsert", timeout=1)
            if job2:
                try:
                    tenant_id = str(job2.get("tenant_id") or "global")
                    payload = job2.get("payload") or {}
                    chunks = payload.get("chunks") or []
                    if chunks:
                        qdrant_service.upsert_knowledge_chunks(tenant_id, chunks)
                except Exception as e:
                    stability_metrics.inc_bg_failure("retry_worker")
                    stability_metrics.inc_bg_retry("retry_worker")
                    log_and_continue(e, "retry_worker.qdrant_upsert", tenant_id, None)
                continue
            # process audit logs
            job3 = retry_queue.dequeue("audit_log", timeout=1)
            if job3:
                try:
                    payload = job3.get("payload") or {}
                    tenant_id_raw = job3.get("tenant_id") or payload.get("tenant_id")
                    # Sanitize UUID fields to avoid DB binding errors
                    import uuid as _uuidmod
                    def _clean_uuid(val):
                        try:
                            if val is None:
                                return None
                            return str(_uuidmod.UUID(str(val)))
                        except Exception:
                            return None
                    tenant_id = _clean_uuid(tenant_id_raw) or "00000000-0000-0000-0000-000000000001"
                    user_id = _clean_uuid(payload.get("user_id"))
                    api_key_id = _clean_uuid(payload.get("api_key_id"))
                    from shared.database.session import SessionLocal as _SL
                    s = _SL()
                    try:
                        from shared.database.models import AuditLog as _Audit
                        rec = _Audit(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            api_key_id=api_key_id,
                            correlation_id=payload.get("correlation_id"),
                            auth_type=payload.get("auth_type"),
                            category=payload.get("category"),
                            action=payload.get("action"),
                            resource=payload.get("resource"),
                            classification=payload.get("classification"),
                            origin=payload.get("origin"),
                            request_hash=payload.get("request_hash"),
                            response_hash=payload.get("response_hash"),
                            success=bool(payload.get("success")),
                            latency_ms=int(payload.get("latency_ms") or 0),
                            model=payload.get("model"),
                            token_input=payload.get("token_input"),
                            token_output=payload.get("token_output"),
                            extra=payload.get("extra") or {},
                        )
                        s.add(rec)
                        s.commit()
                    finally:
                        s.close()
                except Exception as e:
                    stability_metrics.inc_bg_failure("retry_worker")
                    stability_metrics.inc_bg_retry("retry_worker")
                    log_and_continue(e, "retry_worker.audit_persist", tenant_id, None)
                continue
            # flush cost summaries periodically
            now = time.time()
            if int(now) % max(1, cost_cfg.persist_interval_s) == 0:
                try:
                    snap = rolling_cost.snapshot_and_clear()
                    if snap:
                        from shared.database.session import SessionLocal as _SL
                        s = _SL()
                        try:
                            from shared.database.models import CostSummary as _CS
                            for (tenant, model, kind), (tin, tout, usd) in snap.items():
                                cents = int(round(usd * 100.0))
                                rec = _CS(
                                    tenant_id=tenant,
                                    model=model,
                                    kind=kind,
                                    tokens_in=int(tin),
                                    tokens_out=int(tout),
                                    cost_usd=cents,
                                )
                                s.add(rec)
                            s.commit()
                        finally:
                            s.close()
                except Exception as e:
                    stability_metrics.inc_bg_failure("retry_worker")
                    log_and_continue(e, "retry_worker.cost_flush", None, None)

    t1 = threading.Thread(target=_qdrant_health_loop, daemon=True)
    t2 = threading.Thread(target=_retry_worker_loop, daemon=True)
    t1.start()
    t2.start()

    # Start connector scheduler if enabled
    scheduler_thread = None
    if connectors_cfg.enabled and connectors_cfg.scheduler_enabled:
        try:
            # Discover tenants (for demo, include default only); extend to real tenant list in production
            tenants = ["00000000-0000-0000-0000-000000000001"]
            from ai_core.scheduler.scheduler import ConnectorScheduler
            sched = ConnectorScheduler(tenants)
            def _sched_loop():
                try:
                    sched.loop()
                except Exception as e:
                    stability_metrics.inc_bg_failure("scheduler")
                    log_and_continue(e, "connector.scheduler", None, None)
            scheduler_thread = threading.Thread(target=_sched_loop, daemon=True)
            scheduler_thread.start()
        except Exception:
            pass
    yield
    app_logger.info("Shutting down AI Core service...")
    # Cleanup logic here
    stop_flag["stop"] = True

# Startup model validation & uptime
_START_TS = None
def _validate_startup() -> None:
    # JWT secret check is handled in jwt service, but warn here too if weak
    try:
        sec = os.getenv("JWT_SECRET", "")
        if sec and len(sec) < 32:
            app_logger.warning("JWT_SECRET seems weak (<32 chars).")
    except Exception:
        pass
    # Model validation
    model = os.getenv("LLM_MODEL") or os.getenv("RAG_CHAT_MODEL", "gpt-4o-mini")
    if not model:
        raise RuntimeError("LLM_MODEL environment variable must be set.")

# Create FastAPI application
app = FastAPI(
    title="Omnichannel RAG Chatbot - AI Core",
    description="Enterprise-grade RAG-powered conversational AI service",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware (restricted by default unless DEV)
DEV = os.getenv("ENV", "dev").lower() in ("dev", "local", "test")
allow_origins = ["*"] if DEV else [o for o in (os.getenv("ALLOW_ORIGINS", "").split(",")) if o]
if not allow_origins:
    allow_origins = ["http://localhost:3000"] if DEV else []
if not DEV and ("*" in allow_origins):
    app_logger.warning("Wildcard CORS in non-dev environment.")
app.add_middleware(CORSMiddleware, allow_origins=allow_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Add correlation ID middleware
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(AccessControlMiddleware)

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
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    uptime = 0
    try:
        if _START_TS:
            uptime = int((now.timestamp() - _START_TS))
    except Exception:
        uptime = 0
    return {"status": "ok", "time_utc": now.isoformat().replace("+00:00","Z"), "uptime_seconds": uptime}

@app.get("/v1/ready")
async def ready_check():
    from shared.cache.redis import redis_cache
    from shared.database.session import engine
    from sqlalchemy import text as _sql_text
    ok_db = False
    ok_redis = False
    try:
        with engine.connect() as conn:
            conn.execute(_sql_text("SELECT 1"))
            ok_db = True
    except Exception:
        ok_db = False
    try:
        ok_redis = bool(redis_cache.ping())
    except Exception:
        ok_redis = False
    return {"status": "ok" if (ok_db and ok_redis) else "degraded", "db": ok_db, "redis": ok_redis}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

app.include_router(query_router)
app.include_router(whatsapp_router)
app.include_router(internal_router)
app.include_router(teams_router)
app.include_router(telegram_router)
app.include_router(tenant_router)
app.include_router(reranker_router)
app.include_router(apikey_router)
app.include_router(rerank_admin_router)
app.include_router(feedback_router)

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
