"""RAG Service Dependencies

FastAPI dependency functions for RAG/Retrieval components. This module centralizes
lazy one-time initialization for the vector store client and provides cached
singleton dependency providers for downstream endpoints/services.
"""

from functools import lru_cache
from typing import Annotated, Any
import threading
import logging

from fastapi import Depends

from ..core.config import settings
from ..services.document_processing import document_processing_service
from ..services.embedding import embedding_service
from ..services.vector_store import vector_store_service
from ..services.rag import rag_service

logger = logging.getLogger(__name__)

# Module-level one-time init control for vector store client
_vector_store_initialized = False
_vector_store_init_lock = threading.Lock()

def _initialize_vector_store_once() -> None:
    """Thread-safe, idempotent initialization of the vector store client.

    This avoids per-request initialization and ensures the heavy client
    construction happens only once. Index connection/creation should be
    handled in the application startup lifespan (see main.py) to keep
    dependencies pure and fast.
    """
    global _vector_store_initialized
    if _vector_store_initialized:
        return
    with _vector_store_init_lock:
        if _vector_store_initialized:
            return
        api_key = settings.PINECONE_API_KEY
        if not api_key:
            logger.warning("Vector store initialization skipped: PINECONE_API_KEY not set")
            return
        try:
            # Coerce SecretStr -> str if necessary
            if hasattr(api_key, 'get_secret_value'):
                api_key_value = api_key.get_secret_value()
            else:
                api_key_value = str(api_key)
            vector_store_service.initialize_client(api_key_value)
            _vector_store_initialized = True
            logger.info("Vector store client initialized (one-time)")
        except Exception as e:
            logger.error(f"Failed to initialize vector store client: {e}")
            # Don't re-raise to avoid breaking dependency resolution; service will remain uninitialized


@lru_cache(maxsize=1)
def get_document_processing_service() -> Any:
    """Return the singleton document processing service (cached)."""
    return document_processing_service


@lru_cache(maxsize=1)
def get_embedding_service() -> Any:
    """Return the singleton embedding service (cached)."""
    return embedding_service


@lru_cache(maxsize=1)
def get_vector_store_service() -> Any:
    """Return the vector store service singleton (cached).

    Triggers lazy one-time client initialization if required. Index creation
    is handled in app lifespan. If initialization cannot proceed (e.g. missing
    API key), the uninitialized service is still returned so callers can react.
    """
    _initialize_vector_store_once()
    return vector_store_service


@lru_cache(maxsize=1)
def get_rag_service() -> Any:
    """Return the RAG orchestration service singleton (cached)."""
    return rag_service


# Type annotations for dependency injection
DocumentProcessingDep = Annotated[object, Depends(get_document_processing_service)]
EmbeddingServiceDep = Annotated[object, Depends(get_embedding_service)]
VectorStoreDep = Annotated[object, Depends(get_vector_store_service)]
RAGServiceDep = Annotated[object, Depends(get_rag_service)]
