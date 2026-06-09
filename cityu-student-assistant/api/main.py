"""
CityU Student Assistant — FastAPI application entry point.

Run with:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.routes.updates import router as updates_router

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

load_dotenv()


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown hooks)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup tasks before the app accepts requests."""
    logger.info("Starting CityU Student Assistant API...")

    # Pre-warm the embedding model and ChromaDB connection so the first
    # request does not incur a cold-start penalty.
    try:
        from agent.vector_store import get_vector_store
        get_vector_store()
        logger.info("Vector store pre-warmed successfully.")
    except Exception as exc:
        # Non-fatal: the app can still serve /health while the vector store
        # initialises on the first /chat request.
        logger.warning("Vector store pre-warm failed (non-fatal): %s", exc)

    yield  # Application is running

    logger.info("Shutting down CityU Student Assistant API.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CityU Student Assistant API",
    description=(
        "AI-powered academic assistant for City University of Seattle students. "
        "Answers questions about courses, prerequisites, degree requirements, "
        "and academic policies using RAG and structured database queries."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow all origins for local Streamlit development
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(updates_router)


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Redirect users to the interactive API docs."""
    return {
        "message": "CityU Student Assistant API is running.",
        "docs": "/docs",
        "health": "/health",
    }
