"""
RAG Services Module

This module contains all services related to Retrieval-Augmented Generation:
- Document processing (text extraction, chunking)
- Embedding generation (vector creation)
- Vector store operations (Pinecone integration)
- RAG orchestration (retrieval and augmentation)
"""

# Import individual services for external use
# Note: Import errors will be resolved once all service files are created

try:
    from .document_processing import DocumentProcessingService
    from .embedding import EmbeddingService
    from .vector_store import VectorStoreService
    from .rag import RAGService
    
    __all__ = [
        "DocumentProcessingService",
        "EmbeddingService", 
        "VectorStoreService",
        "RAGService"
    ]
except ImportError as e:
    # Graceful handling during development
    print(f"Warning: Some RAG services not available: {e}")
    __all__ = []
