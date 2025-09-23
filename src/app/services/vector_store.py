"""
Vector Store Service

Handles vector database operations for RAG pipeline using Pinecone's integrated text embeddings.

Key behaviors:
- Ingestion strictly uses Pinecone's text-native `upsert_records(namespace, records)` where each record contains:
    {"_id": str, "text": str, ...metadata}
- Retrieval strictly uses Pinecone's `index.search({input: {type: 'text', text: str}, top_k, namespace, filter})`.
- No local embedding generation is performed in this service.

Inputs/Outputs contract:
- upsert_vectors(vectors_data):
    Input: list of { id: str, metadata: { text: str, ... } }. The text is embedded server-side by Pinecone.
    Output: None; raises on failures. Logs counts and sample keys.
- search_similar_vectors(query_text, top_k, filter_metadata):
    Input: query_text (str), top_k (int), optional filter dict. Uses namespace from settings.
    Output: List[VectorSearchResult] sorted by Pinecone score descending.

Error modes:
- If Pinecone SDK doesn't support required text APIs and PINECONE_REQUIRE_TEXT_APIS=True, raise RuntimeError to avoid silent fallbacks.
- If client/index not initialized, ensure_ready() is called; raises if misconfigured.
"""

import asyncio
import logging
import importlib.util
import json
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


def json_safe(obj: Any) -> str:
    """Safely stringify objects for debug logs (truncates to 1000 chars)."""
    try:
        return json.dumps(obj, ensure_ascii=False)[:1000]
    except Exception:
        return str(obj)[:1000]


class VectorSearchResult:
    """Represents a result from Pinecone similarity search.

    Attributes:
        chunk_id: The stored chunk identifier.
        score: Relevance score provided by Pinecone (higher is better).
        text: Retrieved chunk text (from metadata.text).
        metadata: All stored metadata associated with the chunk.
    """
    
    def __init__(self, chunk_id: str, score: float, text: str, metadata: Dict[str, Any]):
        self.chunk_id = chunk_id
        self.score = score
        self.text = text
        self.metadata = metadata


class VectorStoreService:
    """Service for vector database operations using Pinecone text-native APIs."""
    
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
        logger.info(
            f"VectorStoreService init: index={self.index_name}, namespace={self.namespace}, "
            f"cloud={self.cloud}, region={self.region}, model={self.embedding_model}"
        )

    def _have_pinecone(self) -> bool:
        """Detect if pinecone package is available without importing it (IDE-friendly)."""
        return importlib.util.find_spec("pinecone") is not None

    async def ensure_ready(self) -> None:
        """Ensure client and index are initialized based on settings.

        Reads env flags to decide behavior; validates presence of required text APIs when configured.
        """
        if self.client and self.index:
            return
        from ..core.config import settings
        api_key = getattr(settings, "PINECONE_API_KEY", None)
        if not self.client:
            if api_key:
                try:
                    self.initialize_client(api_key.get_secret_value())
                except Exception as e:
                    logger.error(f"Failed to initialize Pinecone client in ensure_ready: {e}")
                    raise
            else:
                raise RuntimeError("PINECONE_API_KEY not configured")
        if not self.index:
            await self.create_index_if_not_exists()

    def initialize_client(self, api_key: str) -> None:
        """
        Initialize Pinecone client with API key.
        
        Args:
            api_key: Pinecone API key
        """
        logger.info("Pinecone client initialization start")
        logger.info(f"🔍 DEBUG: API key length: {len(api_key)}")
        logger.info(f"🔍 DEBUG: API key starts with: {api_key[:10]}...")
        
        try:
            from pinecone import Pinecone  # type: ignore[reportMissingImports]
            logger.info("Pinecone import successful")
            
            self.client = Pinecone(api_key=api_key)
            logger.info("Pinecone client created")
            
            # Test the client by listing indexes
            try:
                indexes = self.client.list_indexes()
                logger.info(f"Available indexes: {[idx.name for idx in indexes]}")
            except Exception as list_error:
                logger.error(f"Failed to list indexes: {list_error}")
            
            logger.info("✅ Pinecone client initialized")
            
        except ImportError as import_error:
            logger.error(f"❌ Pinecone package not installed: {import_error}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to initialize Pinecone client: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise

    async def create_index_if_not_exists(self) -> None:
        """
        Connect to existing Pinecone index. The index is expected to exist already.
        """
        logger.info("Index connection start")
        if not self.client:
            logger.error("❌ Pinecone client not initialized")
            raise RuntimeError("Pinecone client not initialized")
        logger.info(f"🔍 DEBUG: Connecting to index: {self.index_name}")

        try:
            # Check if index exists
            logger.info("Checking if index exists...")
            index_exists = self.client.has_index(self.index_name)
            logger.info(f"Index '{self.index_name}' exists: {index_exists}")

            if index_exists:
                logger.info(f"Connecting to existing Pinecone index: {self.index_name}")
                self.index = self.client.Index(self.index_name)
                logger.info(f"Index object created: {type(self.index)}")
                try:
                    stats = self.index.describe_index_stats()
                    logger.info(f"Index stats: {stats}")
                    logger.info(f"✅ Connected to index: {self.index_name}")
                except Exception as stats_error:
                    logger.error(f"Failed to get index stats: {stats_error}")
            else:
                available_indexes = self.client.list_indexes()
                available_names = [idx.name for idx in available_indexes]
                logger.error(f"❌ Index '{self.index_name}' does not exist")
                logger.error(f"Available indexes: {available_names}")
                raise RuntimeError(
                    f"Pinecone index {self.index_name} not found. Available: {available_names}"
                )
        except Exception as e:
            logger.error(f"❌ Error connecting to index: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise

    async def upsert_vectors(self, vectors_data: List[Dict[str, Any]]) -> None:
        """Upsert chunk records into Pinecone using text-native API."""
        if not vectors_data:
            logger.info("🔍 DEBUG: No vectors to upsert")
            return
        if not self.index:
            logger.warning("Pinecone index not initialized; attempting ensure_ready()")
            await self.ensure_ready()
            if not self.index:
                logger.error("❌ Pinecone index still not initialized after ensure_ready")
                raise RuntimeError("Pinecone index not initialized")

        logger.info(
            f"Upsert start: count={len(vectors_data)}, namespace={self.namespace}, index={self.index_name}"
        )
        from ..core.config import settings
        require_text_apis = getattr(settings, "PINECONE_REQUIRE_TEXT_APIS", True)
        text_field = getattr(settings, "PINECONE_TEXT_FIELD", "text")

        try:
            records = []
            for i, vector in enumerate(vectors_data):
                record = {
                    "_id": vector["id"],
                    text_field: vector["metadata"]["text"],
                    **{k: v for k, v in vector["metadata"].items() if k != "text"},
                }
                records.append(record)
                logger.info(
                    f"Record {i}: id={record['_id']}, text_len={len(record.get(text_field, ''))}"
                )

            logger.info(
                f"Converted {len(records)} records; sample keys: {list(records[0].keys()) if records else 'none'}"
            )
            logger.info("Attempting index.upsert_records (text API)")
            try:
                result = self.index.upsert_records(self.namespace, records)
            except AttributeError as e:
                if require_text_apis:
                    logger.error(
                        "Pinecone SDK missing upsert_records while REQUIRE_TEXT_APIS=True"
                    )
                    raise RuntimeError(
                        "Pinecone SDK lacks text APIs. Please upgrade pinecone-client."
                    ) from e
                logger.warning("upsert_records not available; skipping ingestion per configuration")
                return
            logger.info(f"🔍 DEBUG: Upsert result: {result}")
            logger.info(
                f"✅ Successfully upserted {len(vectors_data)} vectors to namespace '{self.namespace}'"
            )
        except Exception as e:
            logger.error(f"❌ Error upserting vectors: {e}")
            import traceback
            logger.error(f"🔍 DEBUG: Full traceback: {traceback.format_exc()}")
            raise

    async def search_similar_vectors(
        self,
        query_vector: Optional[List[float]] = None,
        query_text: Optional[str] = None,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List['VectorSearchResult']:
        """Search similar chunks using Pinecone text-native search (index.search)."""
        # Ensure index is ready
        if not self.index:
            logger.warning("Pinecone index not initialized; attempting ensure_ready() before query")
            await self.ensure_ready()
            if not self.index:
                logger.error("Pinecone index still not initialized")
                raise RuntimeError("Pinecone index not initialized")

        # Enforce text-native search path (this service is text-native only)
        if not query_text and not query_vector:
            raise ValueError("query_text is required for Pinecone text-native search")

        try:
            from ..core.config import settings
            use_text = getattr(settings, "PINECONE_USE_TEXT_SEARCH", True)
            require_text_apis = getattr(settings, "PINECONE_REQUIRE_TEXT_APIS", True)
            text_field = getattr(settings, "PINECONE_TEXT_FIELD", "text")

            if not use_text:
                logger.error(
                    "PINECONE_USE_TEXT_SEARCH is disabled but no vector path is supported. Enable it."
                )
                raise RuntimeError("Text search disabled but no vector query path provided.")

            # Build search parameters per Pinecone search_records API
            # top_k and filter must be inside the `query` object
            query_obj: Dict[str, Any] = {
                "inputs": {"text": query_text or ""},
                "top_k": int(top_k),
            }
            if filter_metadata:
                query_obj["filter"] = filter_metadata

            search_params: Dict[str, Any] = {
                "namespace": self.namespace,
                "query": query_obj,
                # Optionally specify exact fields to return:
                # "fields": [text_field, "document_id", "source", ...]
                # If omitted, Pinecone returns all fields.
            }

            logger.info(
                "\n".join(
                    [
                        "VectorStore: search()",
                        f"- Namespace: {self.namespace}",
                        f"- TopK: {top_k}",
                        f"- Filter: {json_safe(filter_metadata)}",
                        f"- Query (first 200): {(query_text or '')[:200]}",
                    ]
                )
            )

            # Call the text-native search API; do NOT pass top_k as a top-level kwarg
            try:
                search_results = self.index.search(**search_params)
            except AttributeError as e:
                # If SDK lacks the text-native search API and strict mode is enabled, fail loudly
                if require_text_apis:
                    logger.error("Pinecone SDK missing index.search(text) while REQUIRE_TEXT_APIS=True")
                    raise RuntimeError(
                        "Pinecone SDK lacks text-native search API. Please upgrade pinecone-client."
                    ) from e
                logger.warning("Text search API not available; returning empty results per configuration")
                return []

            # Parse results: index.search returns {'result': {'hits': [...]}, 'usage': {...}}
            results: List[VectorSearchResult] = []
            hits = []

            if isinstance(search_results, dict):
                result_section = search_results.get("result", {})
                hits = result_section.get("hits", [])
                # Fallback: if someone routed to index.query accidentally, support matches shape too
                if not hits and "matches" in search_results:
                    # Legacy/alternative shape (index.query)
                    for match in search_results.get("matches", []):
                        match_id = match.get("id")
                        match_score = match.get("score", 0.0)
                        match_metadata = match.get("metadata", {}) or {}
                        results.append(
                            VectorSearchResult(
                                chunk_id=match_id,
                                score=match_score,
                                text=match_metadata.get(text_field, match_metadata.get("text", "")) or "",
                                metadata=match_metadata,
                            )
                        )
            else:
                # Rare case: SDK returns an object; try attribute access
                result_attr = getattr(search_results, "result", None)
                if result_attr and hasattr(result_attr, "hits"):
                    hits = getattr(result_attr, "hits", []) or []
                elif hasattr(search_results, "matches"):
                    for match in getattr(search_results, "matches", []) or []:
                        match_id = getattr(match, "id", None)
                        match_score = getattr(match, "score", 0.0)
                        match_metadata = getattr(match, "metadata", {}) or {}
                        results.append(
                            VectorSearchResult(
                                chunk_id=match_id or "unknown",  # Provide fallback for None
                                score=match_score,
                                text=match_metadata.get(text_field, match_metadata.get("text", "")) or "",
                                metadata=match_metadata,
                            )
                        )

            # Convert hits (text-native search shape) into VectorSearchResult objects
            for hit in hits:
                hit_id = hit.get("_id")
                hit_score = hit.get("_score", 0.0)
                hit_fields = hit.get("fields", {}) or {}
                results.append(
                    VectorSearchResult(
                        chunk_id=hit_id or "unknown",  # Provide fallback for None
                        score=hit_score,
                        text=hit_fields.get(text_field, hit_fields.get("text", "")) or "",
                        metadata=hit_fields,  # Treat returned fields as metadata
                    )
                )

            logger.info(f"🔍 DEBUG: Processing {len(results)} matches from search results")

            if results:
                lines = [
                    "VectorStore: Matches (sorted by score)",
                    "#  score    id                           doc_id                          text_preview",
                ]
                for i, r in enumerate(sorted(results, key=lambda r: (r.score or 0.0), reverse=True)[:15]):
                    doc_id = str((r.metadata or {}).get("document_id"))
                    preview = (r.text or "").replace("\n", " ")[:100]
                    lines.append(
                        f"{i+1:>2}  {r.score:>6.4f}  {str(r.chunk_id)[:28]:<28}  {doc_id[:30]:<30}  {preview}"
                    )
                if len(results) > 15:
                    lines.append(f"... (+{len(results)-15} more)")
                logger.info("\n".join(lines))

            results.sort(key=lambda r: (r.score or 0.0), reverse=True)
            logger.info(f"Found {len(results)} matches (sorted by score)")
            return results

        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            raise


    async def delete_vectors_by_document(self, document_id: UUID) -> None:
        """Delete all vectors associated with a specific document."""
        if not self.index:
            logger.warning("Pinecone index not initialized; attempting ensure_ready() before delete")
            await self.ensure_ready()
            if not self.index:
                logger.error("Pinecone index still not initialized")
                raise RuntimeError("Pinecone index not initialized")
        try:
            logger.info(
                f"Deleting vectors for document {document_id} in namespace '{self.namespace}'"
            )
            self.index.delete(filter={"document_id": str(document_id)}, namespace=self.namespace)
            logger.info(f"Deleted vectors for document {document_id}")
        except Exception as e:
            logger.error(f"Error deleting vectors for document {document_id}: {e}")
            raise

    async def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector index."""
        if not self.index:
            return {"error": "Pinecone index not initialized", "status": "not_initialized"}
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count if hasattr(stats, "total_vector_count") else 0,
                "namespaces": stats.namespaces if hasattr(stats, "namespaces") else {},
                "dimension": stats.dimension if hasattr(stats, "dimension") else None,
                "status": "connected",
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
