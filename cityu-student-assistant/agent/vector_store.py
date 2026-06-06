"""
ChromaDB vector store initialisation and retriever factory.

The collection ``cityu_docs`` holds all chunked CityU documents.
Embeddings are generated locally using ``sentence-transformers/all-MiniLM-L6-v2``
so no external API key is required.
"""

import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore
from langchain_chroma import Chroma  # type: ignore
from langchain_core.vectorstores import VectorStoreRetriever

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_PERSIST_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "cityu_docs"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Module-level singletons — initialised lazily on first use
_embeddings: Optional[HuggingFaceEmbeddings] = None
_vector_store: Optional[Chroma] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the (cached) HuggingFace embedding model.

    The model is downloaded once and reused for the lifetime of the process.
    """
    global _embeddings
    if _embeddings is None:
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL_NAME)
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Embedding model loaded successfully.")
    return _embeddings


def get_vector_store() -> Chroma:
    """Return the (cached) ChromaDB vector store instance.

    The persistent directory is created automatically if it does not exist.
    """
    global _vector_store
    if _vector_store is None:
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Initialising ChromaDB collection '%s' at %s",
            COLLECTION_NAME,
            CHROMA_PERSIST_DIR,
        )
        _vector_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=str(CHROMA_PERSIST_DIR),
        )
        logger.info("ChromaDB vector store ready.")
    return _vector_store


def get_retriever(k: int = 4) -> VectorStoreRetriever:
    """Return a LangChain retriever over the CityU docs collection.

    Parameters
    ----------
    k : int
        Number of documents to retrieve per query (default 4).

    Returns
    -------
    VectorStoreRetriever
        A LangChain-compatible retriever.
    """
    store = get_vector_store()
    logger.debug("Creating retriever with k=%d", k)
    return store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )


def reset_singletons() -> None:
    """Reset module-level singletons (useful in tests)."""
    global _embeddings, _vector_store
    _embeddings = None
    _vector_store = None
