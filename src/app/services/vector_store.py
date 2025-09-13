"""
Vector Store Service

Handles vector database operations for RAG pipeline.
Provides Pinecone integration for vector storage and similarity search.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class VectorSearchResult:
    """Represents a result from vector similarity search."""
    
    def __init__(self, chunk_id: str, score: float, text: str, metadata: Dict[str, Any]):
        self.chunk_id = chunk_id
        self.score = score
        self.text = text
        self.metadata = metadata


class VectorStoreService:
    """Service for vector database operations using Pinecone."""
    
    def __init__(self, index_name: str = "spek-spruce", namespace: str = "default", 
                 cloud: str = "aws", region: str = "us-east-1", 
                 embedding_model: str = "llama-text-embed-v2"):
        """
        Initialize the vector store service.
        
        Args:
            index_name: Name of the Pinecone index
            namespace: Namespace within the index for data isolation
            cloud: Cloud provider for Pinecone index
            region: Region for Pinecone index
            embedding_model: Embedding model to use with Pinecone
        """
        self.index_name = index_name
        self.namespace = namespace
        self.cloud = cloud
        self.region = region
        self.embedding_model = embedding_model
        self.client = None
        self.index = None
        logger.info(f"Initialized VectorStoreService for index: {index_name}")
    
    def initialize_client(self, api_key: str) -> None:
        """
        Initialize Pinecone client with API key.
        
        Args:
            api_key: Pinecone API key
        """
        logger.info("🔍 DEBUG: Starting Pinecone client initialization...")
        logger.info(f"🔍 DEBUG: API key length: {len(api_key)}")
        logger.info(f"🔍 DEBUG: API key starts with: {api_key[:10]}...")
        
        try:
            from pinecone import Pinecone, ServerlessSpec
            logger.info("🔍 DEBUG: Pinecone import successful")
            
            self.client = Pinecone(api_key=api_key)
            logger.info("🔍 DEBUG: Pinecone client created successfully")
            
            # Test the client by listing indexes
            try:
                indexes = self.client.list_indexes()
                logger.info(f"🔍 DEBUG: Available indexes: {[idx.name for idx in indexes]}")
            except Exception as list_error:
                logger.error(f"🔍 DEBUG: Failed to list indexes: {list_error}")
            
            logger.info("✅ Pinecone client initialized successfully")
            
        except ImportError as import_error:
            logger.error(f"❌ Pinecone package not installed: {import_error}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to initialize Pinecone client: {e}")
            import traceback
            logger.error(f"🔍 DEBUG: Full traceback: {traceback.format_exc()}")
            raise
    
    async def create_index_if_not_exists(self) -> None:
        """
        Connect to existing Pinecone index.
        Since the index was created manually, we just need to connect to it.
        """
        logger.info("🔍 DEBUG: Starting index connection process...")
        
        if not self.client:
            logger.error("❌ Pinecone client not initialized")
            raise RuntimeError("Pinecone client not initialized")
        
        logger.info(f"🔍 DEBUG: Connecting to index: {self.index_name}")
        
        try:
            # Check if index exists
            logger.info("🔍 DEBUG: Checking if index exists...")
            index_exists = self.client.has_index(self.index_name)
            logger.info(f"🔍 DEBUG: Index '{self.index_name}' exists: {index_exists}")
            
            if index_exists:
                logger.info(f"🔍 DEBUG: Connecting to existing Pinecone index: {self.index_name}")
                # Get reference to the existing index
                self.index = self.client.Index(self.index_name)
                logger.info(f"🔍 DEBUG: Index object created: {type(self.index)}")
                
                # Test the connection by getting stats
                try:
                    stats = self.index.describe_index_stats()
                    logger.info(f"🔍 DEBUG: Index stats: {stats}")
                    logger.info(f"✅ Successfully connected to index: {self.index_name}")
                except Exception as stats_error:
                    logger.error(f"🔍 DEBUG: Failed to get index stats: {stats_error}")
                    # Continue anyway, the index object might still work
                    
            else:
                available_indexes = self.client.list_indexes()
                available_names = [idx.name for idx in available_indexes]
                logger.error(f"❌ Index '{self.index_name}' does not exist")
                logger.error(f"🔍 DEBUG: Available indexes: {available_names}")
                raise RuntimeError(f"Pinecone index {self.index_name} not found. Available: {available_names}")
            
        except Exception as e:
            logger.error(f"❌ Error connecting to index: {e}")
            import traceback
            logger.error(f"🔍 DEBUG: Full traceback: {traceback.format_exc()}")
            raise
    
    async def upsert_vectors(self, vectors_data: List[Dict[str, Any]]) -> None:
        """
        Upload vectors to the vector database using Pinecone's new upsert_records API.
        
        Args:
            vectors_data: List of dictionaries containing:
                - id: Unique identifier for the vector
                - values: The embedding vector (optional if using text field)
                - metadata: Additional metadata including 'text' for embedding
        """
        if not vectors_data:
            logger.info("🔍 DEBUG: No vectors to upsert")
            return
        
        if not self.index:
            logger.error("❌ Pinecone index not initialized")
            raise RuntimeError("Pinecone index not initialized")
        
        logger.info(f"🔍 DEBUG: Starting upsert of {len(vectors_data)} vectors")
        logger.info(f"🔍 DEBUG: Index object type: {type(self.index)}")
        logger.info(f"🔍 DEBUG: Namespace: {self.namespace}")
        
        try:
            # Convert our vector format to Pinecone's expected format
            # Following the documentation format exactly
            records = []
            for i, vector in enumerate(vectors_data):
                # Use the new format from Pinecone documentation
                record = {
                    "_id": vector["id"],  # Use _id as per documentation
                    "text": vector["metadata"]["text"],  # This is the key field for embedding
                    **{k: v for k, v in vector["metadata"].items() if k != "text"}  # Other metadata
                }
                records.append(record)
                logger.info(f"🔍 DEBUG: Record {i}: id={record['_id']}, text_length={len(record['text'])}")
            
            logger.info(f"🔍 DEBUG: Converted {len(records)} records for upsert")
            logger.info(f"🔍 DEBUG: Sample record keys: {list(records[0].keys()) if records else 'none'}")
            
            # Use the new upsert_records API as per Pinecone documentation
            logger.info(f"🔍 DEBUG: Calling index.upsert_records with namespace '{self.namespace}'")
            result = self.index.upsert_records(self.namespace, records)
            logger.info(f"🔍 DEBUG: Upsert result: {result}")
            
            logger.info(f"✅ Successfully upserted {len(vectors_data)} vectors to namespace '{self.namespace}'")
            
        except Exception as e:
            logger.error(f"❌ Error upserting vectors: {e}")
            import traceback
            logger.error(f"🔍 DEBUG: Full traceback: {traceback.format_exc()}")
            raise
    
    async def search_similar_vectors(self, query_vector: List[float] = None, query_text: str = None, 
                                   top_k: int = 5, filter_metadata: Optional[Dict[str, Any]] = None) -> List[VectorSearchResult]:
        """
        Search for similar vectors in the database.
        
        Args:
            query_vector: The query embedding vector (optional if using integrated embeddings)
            query_text: The query text (for integrated embedding models)
            top_k: Number of similar vectors to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of VectorSearchResult objects
        """
        if not self.index:
            logger.error("Pinecone index not initialized")
            raise RuntimeError("Pinecone index not initialized")
        
        if not query_vector and not query_text:
            raise ValueError("Either query_vector or query_text must be provided")
        
        try:
            # Prepare query parameters
            query_params = {
                "top_k": top_k,
                "include_metadata": True,
                "namespace": self.namespace
            }
            
            if filter_metadata:
                query_params["filter"] = filter_metadata
            
            # Use vector or text query based on what's provided
            if query_vector:
                query_params["vector"] = query_vector
            elif query_text:
                # For integrated embedding models, use text query
                query_params["queries"] = [{"values": [], "metadata": {"text": query_text}}]
            
            # Execute search
            search_results = self.index.query(**query_params)
            
            # Convert results to VectorSearchResult objects
            results = []
            matches = search_results.matches if hasattr(search_results, 'matches') else search_results.get('matches', [])
            
            for match in matches:
                result = VectorSearchResult(
                    chunk_id=match.id,
                    score=match.score,
                    text=match.metadata.get('text', ''),
                    metadata=match.metadata
                )
                results.append(result)
            
            logger.info(f"Found {len(results)} similar vectors")
            return results
            
        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            raise
    
    async def delete_vectors_by_document(self, document_id: UUID) -> None:
        """
        Delete all vectors associated with a specific document.
        
        Args:
            document_id: UUID of the document whose vectors should be deleted
        """
        if not self.index:
            logger.error("Pinecone index not initialized")
            raise RuntimeError("Pinecone index not initialized")
        
        try:
            # Delete vectors with matching document_id in metadata
            self.index.delete(
                filter={"document_id": str(document_id)},
                namespace=self.namespace
            )
            
            logger.info(f"Deleted vectors for document {document_id}")
            
        except Exception as e:
            logger.error(f"Error deleting vectors for document {document_id}: {e}")
            raise
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector index."""
        if not self.index:
            return {
                "error": "Pinecone index not initialized",
                "status": "not_initialized"
            }
        
        try:
            # Get index statistics from Pinecone
            stats = self.index.describe_index_stats()
            
            return {
                "total_vectors": stats.total_vector_count if hasattr(stats, 'total_vector_count') else 0,
                "namespaces": stats.namespaces if hasattr(stats, 'namespaces') else {},
                "dimension": stats.dimension if hasattr(stats, 'dimension') else None,
                "status": "connected"
            }
            
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {"error": str(e), "status": "error"}


# Create service instance with default configuration
# Configuration will be loaded from settings when the service is used
def create_vector_store_service():
    """Create vector store service with configuration from settings."""
    from ..core.config import settings
    return VectorStoreService(
        index_name=settings.PINECONE_INDEX_NAME,
        namespace=settings.PINECONE_NAMESPACE,
        cloud=settings.PINECONE_CLOUD,
        region=settings.PINECONE_REGION,
        embedding_model=settings.PINECONE_EMBEDDING_MODEL
    )

vector_store_service = create_vector_store_service()
