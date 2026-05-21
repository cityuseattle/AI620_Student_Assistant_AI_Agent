"""
Health-check endpoint.

``GET /health`` returns the service status and the name of the configured
LLM provider.  This endpoint is used by the Streamlit frontend to display
the current provider in the sidebar.
"""

import logging

from fastapi import APIRouter

from agent.llm_config import get_llm_provider_name
from api.schemas import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    tags=["Monitoring"],
)
async def health_check() -> HealthResponse:
    """Return the service status and active LLM provider.

    Returns
    -------
    HealthResponse
        ``{"status": "ok", "llm_provider": "<provider>"}``
    """
    provider = get_llm_provider_name()
    logger.debug("Health check requested — provider: %s", provider)
    return HealthResponse(status="ok", llm_provider=provider)
