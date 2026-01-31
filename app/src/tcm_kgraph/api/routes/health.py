"""Health check endpoints."""

from datetime import datetime

from fastapi import APIRouter

from tcm_kgraph import __version__
from tcm_kgraph.api.dependencies import ContainerDep
from tcm_kgraph.models.schemas import HealthResponse, HealthStatus


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(container: ContainerDep) -> HealthResponse:
    """
    Check application health status.

    Returns the overall health status and individual component statuses.
    """
    components: dict[str, HealthStatus] = {}

    # Check Neo4j
    try:
        await container.neo4j_client.verify_connectivity()
        components["neo4j"] = HealthStatus.HEALTHY
    except Exception:
        components["neo4j"] = HealthStatus.UNHEALTHY

    # Determine overall status
    if all(s == HealthStatus.HEALTHY for s in components.values()):
        overall_status = HealthStatus.HEALTHY
    elif any(s == HealthStatus.UNHEALTHY for s in components.values()):
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.UNHEALTHY

    return HealthResponse(
        status=overall_status,
        version=__version__,
        timestamp=datetime.now(),
        components=components,
    )


@router.get("/ready")
async def readiness_check(container: ContainerDep) -> dict[str, bool]:
    """
    Check if the application is ready to serve requests.

    Returns 200 if ready, 503 if not ready.
    """
    try:
        await container.neo4j_client.verify_connectivity()
        return {"ready": True}
    except Exception:
        return {"ready": False}


@router.get("/live")
async def liveness_check() -> dict[str, bool]:
    """
    Check if the application is alive.

    Simple liveness probe that always returns true if the server is running.
    """
    return {"alive": True}
