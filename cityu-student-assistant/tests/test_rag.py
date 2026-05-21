"""
Tests for the ChromaDB vector store and RAG retriever.

These tests use an in-memory / temporary ChromaDB instance so they do not
pollute the production ``chroma_db/`` directory.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is on the path when running pytest from any directory
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_chroma_dir(tmp_path: Path):
    """Return a temporary directory for ChromaDB persistence."""
    return tmp_path / "chroma_test"


@pytest.fixture()
def vector_store(tmp_chroma_dir: Path):
    """Create a fresh ChromaDB vector store in a temp directory."""
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    store = Chroma(
        collection_name="test_cityu_docs",
        embedding_function=embeddings,
        persist_directory=str(tmp_chroma_dir),
    )
    return store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVectorStoreInit:
    """Tests for ChromaDB initialisation."""

    def test_vector_store_creates_collection(self, vector_store) -> None:
        """Vector store should initialise without raising an exception."""
        assert vector_store is not None

    def test_empty_store_returns_no_results(self, vector_store) -> None:
        """An empty collection should return an empty list for any query."""
        retriever = vector_store.as_retriever(search_kwargs={"k": 4})
        results = retriever.invoke("AI620 prerequisites")
        assert results == []

    def test_add_and_retrieve_document(self, vector_store) -> None:
        """Documents added to the store should be retrievable."""
        from langchain_core.documents import Document

        # Add a dummy CityU document
        doc = Document(
            page_content=(
                "AI620 Machine Learning for AI is a core course in the MSAI "
                "program. The prerequisite for AI620 is AI510."
            ),
            metadata={"source": "test_catalog.txt", "chunk_index": 0},
        )
        vector_store.add_documents([doc])

        retriever = vector_store.as_retriever(search_kwargs={"k": 4})
        results = retriever.invoke("AI620 prerequisites")

        assert len(results) >= 1
        assert "AI620" in results[0].page_content

    def test_retriever_returns_at_most_k_results(self, vector_store) -> None:
        """Retriever should honour the k parameter."""
        from langchain_core.documents import Document

        docs = [
            Document(
                page_content=f"CityU course chunk number {i}.",
                metadata={"source": "catalog.txt", "chunk_index": i},
            )
            for i in range(10)
        ]
        vector_store.add_documents(docs)

        k = 3
        retriever = vector_store.as_retriever(search_kwargs={"k": k})
        results = retriever.invoke("CityU course")
        assert len(results) <= k

    def test_metadata_is_preserved(self, vector_store) -> None:
        """Source metadata should survive the round-trip through ChromaDB."""
        from langchain_core.documents import Document

        doc = Document(
            page_content="Financial aid at CityU is available for all students.",
            metadata={"source": "financial_aid_guide.pdf", "chunk_index": 5},
        )
        vector_store.add_documents([doc])

        retriever = vector_store.as_retriever(search_kwargs={"k": 1})
        results = retriever.invoke("financial aid")

        assert len(results) >= 1
        assert results[0].metadata.get("source") == "financial_aid_guide.pdf"


class TestGetRetriever:
    """Tests for the module-level get_retriever() factory."""

    def test_get_retriever_returns_retriever(self, tmp_chroma_dir: Path) -> None:
        """get_retriever() should return a LangChain VectorStoreRetriever."""
        from langchain_core.vectorstores import VectorStoreRetriever

        # Patch CHROMA_PERSIST_DIR to point to the temp directory
        with patch("agent.vector_store.CHROMA_PERSIST_DIR", tmp_chroma_dir):
            from agent.vector_store import get_retriever, reset_singletons
            reset_singletons()
            retriever = get_retriever(k=2)
            assert isinstance(retriever, VectorStoreRetriever)
            reset_singletons()
