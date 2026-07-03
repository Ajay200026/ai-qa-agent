import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.automation.browser import browser_manager
from app.automation.playwright_paths import ensure_playwright_browsers_path
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import setup_logging
from app.core.security import validate_fernet_key
from app.knowledge.neo4j_client import neo4j_client
from app.services.salesforce_oauth_redirect import oauth_redirect_server

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.debug)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    validate_fernet_key()

    try:
        await neo4j_client.connect()
    except Exception as exc:
        logger.warning("Neo4j connection failed (will retry on use): %s", exc)

    try:
        from app.services.salesforce_oauth import ensure_oauth_redirect_server

        await ensure_oauth_redirect_server()
    except Exception as exc:
        logger.warning("Salesforce OAuth redirect server not started: %s", exc)

    yield

    await oauth_redirect_server.stop()
    await browser_manager.stop()
    await neo4j_client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    ensure_playwright_browsers_path(settings.playwright_browsers_path)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    def cors_headers(request: Request) -> dict[str, str]:
        origin = request.headers.get("origin")
        if origin and origin in settings.cors_origin_list:
            return {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
            }
        return {}

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
            headers=cors_headers(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
            headers=cors_headers(request),
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    @app.get("/health")
    async def health():
        return {"status": "healthy", "app": settings.app_name}

    return app


app = create_app()
