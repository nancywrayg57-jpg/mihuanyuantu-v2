"""
AOJU Backend - Main Application Entry
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import all models to ensure SQLAlchemy relationships are resolved
import app.domain  # noqa: F401
from app.api.v1 import api_router
from app.core.composition import install_routes, run_lifecycle_phase, translate_exception
from app.core.config import settings
from app.core.csrf_protection import enforce_cookie_csrf
from app.core.exceptions import AOJUException
from app.core.logger import get_logger, setup_logging
from app.core.response import AppORJSONResponse
from app.core.scheduler import start_scheduler, stop_scheduler
from app.core.security_headers import apply_security_headers
from app.core.trusted_proxy import enforce_trusted_proxy, resolve_requested_host
from app.domain.credits.schema_compat import ensure_credit_transaction_idempotency_schema
from app.domain.operation_logs.middleware import OperationLogMiddleware
from app.infrastructure.cache import close_redis_cache
from app.infrastructure.database import close_db, get_db_context, init_db

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    is_pytest = settings.is_pytest_runtime
    # DB 前的业务模块启动准备。**这里不出现业务名**——装什么归组合层（app/plugins，纯 base 没有）
    await run_lifecycle_phase("run_plugin_startup", app)

    if settings.AUTO_INIT_DB and not is_pytest:
        try:
            await init_db()
            logger.info("Database auto-init completed (AUTO_INIT_DB=true)")
        except Exception:
            logger.exception("Database auto-init failed")

    if settings.AUTO_SEED_DATA and not is_pytest:
        try:
            from scripts.seed_data import seed_initial_data  # type: ignore

            await seed_initial_data()
            logger.info("Database seed completed (AUTO_SEED_DATA=true)")
        except Exception:
            logger.exception("Database seed failed")

    if not is_pytest:
        try:
            async with get_db_context() as db:
                repair_result = await ensure_credit_transaction_idempotency_schema(db)
            if repair_result.get("column_added") or repair_result.get("index_added"):
                logger.info("Credits schema compatibility repair completed", **repair_result)
        except Exception:
            logger.exception("Credits schema compatibility repair failed")

    # Start scheduled tasks (skip in pytest)
    if not is_pytest:
        try:
            await start_scheduler()
            logger.info("Scheduler started successfully")
        except Exception:
            logger.exception("Scheduler start failed")

    # 必须位于 scheduler 启动尝试之后；具体恢复哪些任务归组合层。best-effort，不让应用因此起不来
    if not is_pytest:
        try:
            await run_lifecycle_phase("run_plugin_after_scheduler", app)
        except Exception:
            logger.exception("Plugin after-scheduler hook failed")

    # OPS-QUALITY D1 / IA_C6：无共享 Redis 时菜单版本仅为进程内计数，避免误判为多 worker 已自动一致。
    if settings.REDIS_ENABLED_EFFECTIVE:
        logger.info(
            "REDIS_ENABLED menu_version=shared_redis",
            redis_enabled=True,
        )
    else:
        logger.info(
            "REDIS_DISABLED menu_version=process_local",
            redis_enabled=False,
            ops_note=(
                "菜单 reconcile / 授权变更后须滚动重启全部 API worker；"
                "同进程 bump 可变新，多 worker 无共享 Redis 不自动跨进程一致"
            ),
        )

    yield

    # Shutdown
    await run_lifecycle_phase("run_plugin_shutdown", app)

    # Stop scheduler first
    if not is_pytest:
        try:
            await stop_scheduler()
            logger.info("Scheduler stopped successfully")
        except Exception:
            logger.exception("Scheduler stop failed")

    await close_redis_cache()
    await close_db()


def create_app() -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AOJUAI - AI Application Access and Permission Management Platform",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG else None,
        docs_url=f"{settings.API_V1_PREFIX}/docs" if settings.DEBUG else None,
        redoc_url=f"{settings.API_V1_PREFIX}/redoc" if settings.DEBUG else None,
        default_response_class=AppORJSONResponse,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Operation logs (best-effort, DB persistence)
    app.add_middleware(OperationLogMiddleware)

    # Exception handlers
    @app.exception_handler(AOJUException)
    async def aoju_exception_handler(request: Request, exc: AOJUException):
        """Handle custom AOJU exceptions"""
        logger.warning(
            "aoju_exception",
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            path=request.url.path,
            method=request.method,
        )
        return AppORJSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all uncaught exceptions"""
        # 业务异常翻译是 best-effort：translator 自己坏了也不能盖住原始异常
        try:
            translated_exc = translate_exception(exc)
        except Exception:
            translated_exc = None
        if translated_exc is not None:
            logger.warning(
                "plugin_exception_translated",
                code=translated_exc.code,
                message=translated_exc.message,
                status_code=translated_exc.status_code,
                path=request.url.path,
                method=request.method,
            )
            return AppORJSONResponse(
                status_code=translated_exc.status_code,
                content={
                    "success": False,
                    "code": translated_exc.code,
                    "message": translated_exc.message,
                    "details": translated_exc.details,
                },
            )
        logger.error(
            "uncaught_exception",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
            method=request.method,
            exc_info=True,
        )
        return AppORJSONResponse(
            status_code=500,
            content={
                "success": False,
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred" if not settings.DEBUG else str(exc),
                "details": None,
            },
        )

    @app.middleware("http")
    async def trusted_proxy_middleware(request: Request, call_next):
        requested_host = resolve_requested_host(
            headers=request.headers,
            fallback_host=request.url.hostname,
        )
        try:
            enforce_trusted_proxy(
                headers=request.headers,
                client_host=request.client.host if request.client else None,
                requested_host=requested_host,
                shared_secret=settings.AOJ_PROXY_SHARED_SECRET,
                is_pytest=settings.is_pytest_runtime,
            )
        except AOJUException as exc:
            logger.warning(
                "trusted_proxy_request_rejected",
                path=request.url.path,
                host=requested_host,
                client_host=request.client.host if request.client else None,
                code=exc.code,
                message=exc.message,
            )
            return apply_security_headers(
                AppORJSONResponse(
                    status_code=exc.status_code,
                    content={
                        "success": False,
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    },
                ),
                request_path=request.url.path,
                request_headers=request.headers,
                request_scheme=request.url.scheme,
            )
        try:
            enforce_cookie_csrf(request)
        except AOJUException as exc:
            logger.warning(
                "cookie_csrf_request_rejected",
                path=request.url.path,
                host=requested_host,
                method=request.method,
                code=exc.code,
                message=exc.message,
            )
            return apply_security_headers(
                AppORJSONResponse(
                    status_code=exc.status_code,
                    content={
                        "success": False,
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    },
                ),
                request_path=request.url.path,
                request_headers=request.headers,
                request_scheme=request.url.scheme,
            )

        response = await call_next(request)
        return apply_security_headers(
            response,
            request_path=request.url.path,
            request_headers=request.headers,
            request_scheme=request.url.scheme,
        )

    # Include routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    install_routes(app)  # 组合层按需挂载业务路由（纯 base no-op）

    # Static files for uploads
    static_dir = Path(settings.UPLOAD_DIR).parent
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount(settings.STATIC_URL, StaticFiles(directory=str(static_dir)), name="static")

    # Health check
    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=8000,
        reload=settings.DEBUG,
    )
