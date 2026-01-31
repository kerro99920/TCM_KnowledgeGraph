"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tcm_kgraph import __version__
from tcm_kgraph.api.routes import health, knowledge, chat
from tcm_kgraph.api.middleware import setup_middleware
from tcm_kgraph.core.config import get_settings
from tcm_kgraph.core.dependencies import get_container, cleanup_container
from tcm_kgraph.core.logging import setup_logging, get_logger


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events for resource initialization
    and cleanup.
    """
    settings = get_settings()

    # Setup logging
    setup_logging(
        level=settings.log_level,
        format_type=settings.log_format,
    )

    logger.info(f"Starting TCM Knowledge Graph API v{__version__}")

    # Initialize container and verify connections
    container = get_container()

    try:
        # Verify Neo4j connectivity
        await container.neo4j_client.verify_connectivity()
        logger.info("Neo4j connection verified")
    except Exception as e:
        logger.warning(f"Neo4j connection failed: {e}")

    # Store container in app state
    app.state.container = container

    yield

    # Cleanup on shutdown
    logger.info("Shutting down TCM Knowledge Graph API")
    await cleanup_container()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    app = FastAPI(
        title="TCM Knowledge Graph API",
        description=(
            "中医知识图谱API - Traditional Chinese Medicine Knowledge Graph API\n\n"
            "提供中医药知识图谱查询、智能问答和信息检索服务。"
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Setup custom middleware
    setup_middleware(app)

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(
        knowledge.router,
        prefix="/api/v1/knowledge",
        tags=["Knowledge Graph"],
    )
    app.include_router(
        chat.router,
        prefix="/api/v1/chat",
        tags=["Chat"],
    )

    return app


def main() -> None:
    """Run the API server using uvicorn."""
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "tcm_kgraph.api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=settings.log_level == "DEBUG",
        log_level=settings.log_level.lower(),
    )


# Create app instance for direct uvicorn usage
app = create_app()
