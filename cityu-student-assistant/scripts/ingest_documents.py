"""
Document ingestion script for the CityU Student Assistant.

Loads all .pdf, .txt, and .md files from ``data/raw/``, splits them into
chunks, embeds them with sentence-transformers, and upserts into ChromaDB.

Usage
-----
    python scripts/ingest_documents.py [--raw-dir PATH] [--clear]

Options
-------
--raw-dir PATH  Override the default raw documents directory (data/raw/).
--clear         Drop and recreate the ChromaDB collection before ingestion.
"""

import argparse
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow running from any working directory
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402
from langchain_community.document_loaders import (  # noqa: E402
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document  # noqa: E402

from agent.vector_store import get_vector_store  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("ingest_documents")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50
BATCH_SIZE = 100  # upsert in batches to avoid memory spikes

SUPPORTED_EXTENSIONS: dict[str, type] = {
    ".pdf": PyPDFLoader,
    ".txt": TextLoader,
    ".md": UnstructuredMarkdownLoader,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_documents_from_dir(raw_dir: Path) -> list[Document]:
    """Load all supported documents from *raw_dir*.

    Parameters
    ----------
    raw_dir : Path
        Directory containing raw documents (.pdf, .txt, .md).

    Returns
    -------
    list[Document]
        Flat list of LangChain Document objects with ``source`` metadata.

    Raises
    ------
    FileNotFoundError
        If *raw_dir* does not exist.
    """
    if not raw_dir.exists():
        raise FileNotFoundError(
            f"Raw documents directory not found: {raw_dir}\n"
            "Please create the directory and add your CityU documents."
        )

    all_docs: list[Document] = []
    files = sorted(raw_dir.rglob("*"))

    supported_files = [f for f in files if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not supported_files:
        logger.warning(
            "No supported files (.pdf, .txt, .md) found in %s. "
            "Add documents and re-run this script.",
            raw_dir,
        )
        return []

    logger.info("Found %d file(s) to ingest.", len(supported_files))

    for file_path in supported_files:
        loader_cls = SUPPORTED_EXTENSIONS[file_path.suffix.lower()]
        logger.info("Loading: %s", file_path.name)
        try:
            loader = loader_cls(str(file_path))
            docs = loader.load()
            # Normalise metadata
            for doc in docs:
                doc.metadata["source"] = file_path.name
            all_docs.extend(docs)
            logger.info("  → %d page(s) loaded from %s", len(docs), file_path.name)
        except Exception as exc:
            logger.error("  ✗ Failed to load %s: %s", file_path.name, exc)

    logger.info("Total pages loaded: %d", len(all_docs))
    return all_docs


def split_documents(docs: list[Document]) -> list[Document]:
    """Split documents into smaller chunks for embedding.

    Parameters
    ----------
    docs : list[Document]
        Raw documents as loaded by LangChain loaders.

    Returns
    -------
    list[Document]
        Chunked documents with ``chunk_index`` added to metadata.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
    )

    chunks = splitter.split_documents(docs)

    # Track per-source chunk indices for citation purposes
    source_counters: dict[str, int] = {}
    for chunk in chunks:
        source = chunk.metadata.get("source", "unknown")
        idx = source_counters.get(source, 0)
        chunk.metadata["chunk_index"] = idx
        source_counters[source] = idx + 1

    logger.info(
        "Split %d document page(s) into %d chunk(s) "
        "(chunk_size=%d, overlap=%d).",
        len(docs),
        len(chunks),
        CHUNK_SIZE,
        CHUNK_OVERLAP,
    )
    return chunks


def upsert_chunks(chunks: list[Document], clear: bool = False) -> int:
    """Embed and upsert document chunks into ChromaDB.

    Parameters
    ----------
    chunks : list[Document]
        Chunked documents to embed and store.
    clear : bool
        If True, delete all existing documents from the collection first.

    Returns
    -------
    int
        Total number of chunks successfully upserted.
    """
    store = get_vector_store()

    if clear:
        logger.warning("--clear flag set: deleting all existing documents from ChromaDB.")
        try:
            store.delete_collection()
            # Re-initialise after deletion
            from agent.vector_store import reset_singletons
            reset_singletons()
            store = get_vector_store()
            logger.info("Collection cleared and recreated.")
        except Exception as exc:
            logger.error("Failed to clear collection: %s", exc)

    total_upserted = 0

    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[batch_start : batch_start + BATCH_SIZE]
        batch_end = batch_start + len(batch)
        logger.info(
            "Upserting batch %d–%d of %d…",
            batch_start + 1,
            batch_end,
            len(chunks),
        )
        try:
            store.add_documents(batch)
            total_upserted += len(batch)
        except Exception as exc:
            logger.error("Failed to upsert batch %d–%d: %s", batch_start + 1, batch_end, exc)

    return total_upserted


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest CityU documents into the ChromaDB vector store.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Directory containing raw .pdf/.txt/.md documents.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the existing ChromaDB collection before ingestion.",
    )
    return parser.parse_args()


def main() -> None:
    """Main ingestion pipeline."""
    args = parse_args()
    logger.info("=" * 60)
    logger.info("CityU Document Ingestion Pipeline")
    logger.info("Raw directory : %s", args.raw_dir)
    logger.info("Clear first   : %s", args.clear)
    logger.info("=" * 60)

    # Step 1: Load
    try:
        docs = load_documents_from_dir(args.raw_dir)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    if not docs:
        logger.info("No documents to ingest. Exiting.")
        sys.exit(0)

    # Step 2: Split
    chunks = split_documents(docs)

    if not chunks:
        logger.info("No chunks produced. Exiting.")
        sys.exit(0)

    # Step 3: Embed & Upsert
    upserted = upsert_chunks(chunks, clear=args.clear)

    logger.info("=" * 60)
    logger.info("Ingestion complete!")
    logger.info("  Documents loaded : %d", len(docs))
    logger.info("  Chunks produced  : %d", len(chunks))
    logger.info("  Chunks upserted  : %d", upserted)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
