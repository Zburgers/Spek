"""
RAG Service Dependencies

FastAPI dependency functions for RAG services.
These follow the existing dependency injection patterns in the codebase.
"""

from typing import Annotated
from fastapi import Depends

from ..core.config import settings
from ..services.document_processing import document_processing_service
from ..services.embedding import embedding_service
from ..services.vector_store import vector_store_service
from ..services.rag import rag_service


def get_document_processing_service():
    """Get document processing service instance."""
    return document_processing_service


def get_embedding_service():
    """Get embedding service instance."""
    return embedding_service


def get_vector_store_service():
    """Get vector store service instance."""
    # Initialize with API key if available
    if settings.PINECONE_API_KEY:
        vector_store_service.initialize_client(settings.PINECONE_API_KEY.get_secret_value())
        # Create index if it doesn't exist (async operation, will be handled later)
        # This could be moved to an app startup event
    return vector_store_service


def get_rag_service():
    """Get RAG service instance."""
    return rag_service


# Type annotations for dependency injection
DocumentProcessingDep = Annotated[object, Depends(get_document_processing_service)]
EmbeddingServiceDep = Annotated[object, Depends(get_embedding_service)]
VectorStoreDep = Annotated[object, Depends(get_vector_store_service)]
RAGServiceDep = Annotated[object, Depends(get_rag_service)]
