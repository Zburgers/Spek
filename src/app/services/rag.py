"""
RAG (Retrieval-Augmented Generation) Service

Coordinates retrieval from Pinecone and prompt augmentation for the LLM.

Contract:
- retrieve_context(query, user_id, document_ids?):
    Input: query text, user UUID, optional document filters.
    Output: RAGResult with: retrieved_chunks (sorted by Pinecone score), concatenated context, augmented_prompt, metadata.
- get_context_for_documents(query, document_ids):
    Input: query text + list of document UUIDs.
    Output: dict with context, sources, and counters.

Notes:
- Retrieval now uses Pinecone text-native search via VectorStoreService; no local embeddings or MMR reranking.
- Results are already relevance-ranked by Pinecone; we only sort by score for stability and cap by context length.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

from .vector_store import vector_store_service, VectorSearchResult

logger = logging.getLogger(__name__)


class RAGResult:
    """Represents the result of a RAG query."""
    
    def __init__(self, retrieved_chunks: List[VectorSearchResult], context: str, 
                 augmented_prompt: str, metadata: Dict[str, Any]):
        self.retrieved_chunks = retrieved_chunks
        self.context = context
        self.augmented_prompt = augmented_prompt
        self.metadata = metadata


class RAGService:
    """Service for orchestrating Retrieval-Augmented Generation."""
    
    def __init__(
        self,
        max_context_length: int = 4000,
        top_k_retrieval: int = 5,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 60,
    cache_max_entries: int = 256,
    min_score: float = 0.0,
    max_per_document: int = 3,
    ):
        """
        Initialize the RAG service.
        
        Args:
            max_context_length: Maximum character length for context
            top_k_retrieval: Number of top similar chunks to retrieve
            cache_enabled: Enable in-memory retrieval caching
            cache_ttl_seconds: Cache entry TTL in seconds
            cache_max_entries: Max number of cached entries
            min_score: Drop results with score below this threshold (0 disables)
            max_per_document: Cap chunks from a single document after reranking
        """
        self.max_context_length = max_context_length
        self.top_k_retrieval = top_k_retrieval
        self.cache_enabled = cache_enabled
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache_max_entries = cache_max_entries
        self.min_score = min_score
        self.max_per_document = max_per_document
        # cache: key -> (timestamp, RAGResult)
        self._cache: Dict[str, Tuple[float, RAGResult]] = {}
        logger.info("Initialized RAGService")
    
    async def retrieve_context(self, query: str, user_id: UUID,
                             document_ids: Optional[List[UUID]] = None) -> RAGResult:
        """
        Retrieve relevant context for a user query.
        
        Args:
            query: The user's question/query
            user_id: ID of the user making the query
            document_ids: Optional list of document IDs to limit search to
            
        Returns:
            RAGResult containing retrieved chunks and formatted context
        """
        try:
            logger.info(
                "\n".join([
                    "RAG: Retrieve context",
                    f"- Query (first 200): {query[:200]}",
                    f"- User: {user_id}",
                    f"- Document filters: {', '.join(str(d) for d in document_ids) if document_ids else 'ALL'}",
                ])
            )
            # Cache lookup
            cache_key = self._make_cache_key(query, user_id, document_ids)
            now = time.time()
            if self.cache_enabled and cache_key in self._cache:
                ts, cached = self._cache[cache_key]
                if now - ts <= self.cache_ttl_seconds:
                    logger.info("Cache hit for RAG retrieve_context")
                    return cached
                else:
                    # expired
                    self._cache.pop(cache_key, None)
            
            # Step 1: Prepare metadata filters
            filter_metadata: Dict[str, Any] = {"user_id": str(user_id)}
            if document_ids:
                logger.info(f"Filtering RAG context by {len(document_ids)} document(s).")
                filter_metadata["document_id"] = {"$in": [str(d) for d in document_ids]}
            
            # Step 2: Search for similar vectors via Pinecone text search
            prefetch_k = self.top_k_retrieval
            similar_chunks = await vector_store_service.search_similar_vectors( # type: ignore
                query_text=query,
                top_k=prefetch_k,
                filter_metadata=filter_metadata,
            )

            # Log raw search summary
            if similar_chunks:
                lines = [
                    "RAG: Pinecone search results",
                    f"- Matches: {len(similar_chunks)} (top_k={prefetch_k})",
                ]
                for i, c in enumerate(similar_chunks[:10]):
                    doc_id = c.metadata.get("document_id")
                    file_name = c.metadata.get("file_name")
                    text_preview = (c.text or "").replace("\n", " ")[:180]
                    lines.append(f"  {i+1}. score={c.score:.4f} doc={doc_id} file={file_name} text='{text_preview}...'")
                if len(similar_chunks) > 10:
                    lines.append(f"  ... (+{len(similar_chunks)-10} more)")
                logger.info("\n".join(lines))
            else:
                logger.info("RAG: Pinecone search returned 0 matches")

            # Step 2.1: Filter by min score if configured
            if self.min_score > 0:
                before = len(similar_chunks)
                similar_chunks = [c for c in similar_chunks if c.score is not None and c.score >= self.min_score]
                logger.info(f"Filtered chunks by score >= {self.min_score}: {before} -> {len(similar_chunks)}")

            # Step 2.2: Cap per document
            if self.max_per_document > 0:
                per_doc: Dict[str, int] = {}
                capped: List[VectorSearchResult] = []
                for c in similar_chunks:
                    doc_id = str(c.metadata.get("document_id"))
                    count = per_doc.get(doc_id, 0)
                    if count < self.max_per_document:
                        capped.append(c)
                        per_doc[doc_id] = count + 1
                similar_chunks = capped
            
            # Step 3: Format context from retrieved chunks
            context = self._format_context(similar_chunks)
            logger.info(
                "\n".join([
                    "RAG: Built context",
                    f"- Chunks used: {len(similar_chunks)}",
                    f"- Context length: {len(context)}",
                    "- Context preview:\n" + (context[:2000] + ("..." if len(context) > 2000 else ""))
                ])
            )
            
            # Step 4: Create augmented prompt
            augmented_prompt = self._create_augmented_prompt(query, context)
            logger.info(
                "\n".join([
                    "RAG: Augmented prompt",
                    f"- Prompt length: {len(augmented_prompt)}",
                    "- Prompt preview:\n" + (augmented_prompt[:2000] + ("..." if len(augmented_prompt) > 2000 else ""))
                ])
            )
            
            # Step 5: Prepare metadata
            metadata = {
                "chunks_retrieved": len(similar_chunks),
                "context_length": len(context),
                "query_length": len(query),
                "user_id": str(user_id),
                "document_filter": [str(d) for d in document_ids] if document_ids else None
            }
            
            logger.info(f"RAG: Retrieved {len(similar_chunks)} chunks, context length: {len(context)}")
            
            result = RAGResult(
                retrieved_chunks=similar_chunks,
                context=context,
                augmented_prompt=augmented_prompt,
                metadata=metadata
            )
            # Cache store
            if self.cache_enabled:
                if len(self._cache) >= self.cache_max_entries:
                    # evict oldest
                    oldest_key = min(self._cache.items(), key=lambda kv: kv[1][0])[0]
                    self._cache.pop(oldest_key, None)
                self._cache[cache_key] = (now, result)
            return result
            
        except Exception as e:
            logger.error(f"Error in retrieve_context: {e}")
            raise

    def _make_cache_key(self, query: str, user_id: UUID, document_ids: Optional[List[UUID]]) -> str:
        doc_part = ",".join(sorted([str(d) for d in document_ids])) if document_ids else "*"
        return f"u:{user_id}|q:{query.strip().lower()}|d:{doc_part}"

    # MMR and local cosine helpers removed for Pinecone-native ranking
    
    def _format_context(self, chunks: List[VectorSearchResult]) -> str:
        """
        Format retrieved chunks into a coherent context string.
        
        Args:
            chunks: List of retrieved vector search results
            
        Returns:
            Formatted context string
        """
        if not chunks:
            return ""
        
        context_parts = []
        current_length = 0
        
        for i, chunk in enumerate(chunks):
            # Format chunk with source information
            chunk_text = f"[Source {i+1}: {chunk.metadata.get('file_name', 'Unknown')}]\n{chunk.text}\n"
            
            # Check if adding this chunk would exceed max context length
            if current_length + len(chunk_text) > self.max_context_length:
                break
            
            context_parts.append(chunk_text)
            current_length += len(chunk_text)
        
        return "\n".join(context_parts)
    
    def _create_augmented_prompt(self, query: str, context: str) -> str:
        """
        Create an augmented prompt combining query and retrieved context.
        
        Args:
            query: Original user query
            context: Retrieved and formatted context
            
        Returns:
            Augmented prompt for the LLM
        """
        if not context.strip():
            # If no context retrieved, return original query
            return query
        
        augmented_prompt = f"""Based on the following context from the user's documents, please answer the question. If the context doesn't contain enough information to answer the question, please say so clearly.

Context:
{context}

Question: {query}

Please provide a comprehensive answer based on the context provided above."""
        
        return augmented_prompt

    async def delete_document_vectors(self, document_id: UUID) -> None:
        """Delete all vectors associated with a given document ID.

        This is a thin wrapper over the vector store service to keep callers
        decoupled from the underlying implementation.
        """
        try:
            await vector_store_service.delete_vectors_by_document(document_id) # type: ignore
            logger.info(f"Deleted vectors for document {document_id}")
        except Exception as e:
            logger.error(f"Error deleting vectors for document {document_id}: {e}")
            raise

    # ------------------------------------------------------------------
    # Cache invalidation helpers
    # ------------------------------------------------------------------
    def invalidate_cache_for_user(self, user_id: UUID) -> int:
        """Invalidate all cached retrievals for a specific user.

        Returns number of entries removed.
        """
        if not self.cache_enabled or not self._cache:
            return 0
        prefix = f"u:{user_id}|"
        to_delete = [k for k in self._cache if k.startswith(prefix)]
        for k in to_delete:
            self._cache.pop(k, None)
        if to_delete:
            logger.info(f"RAG cache invalidated for user {user_id}: {len(to_delete)} entries removed")
        return len(to_delete)

    def invalidate_cache_for_document(self, document_id: UUID, user_id: Optional[UUID] = None) -> int:
        """Invalidate cached retrievals that could include a document.

        If user_id provided, clears that user's entries (safe, small cache). Otherwise,
        removes entries whose doc filter explicitly contains the document id or '*' (all docs).
        Returns number of entries removed.
        """
        if not self.cache_enabled or not self._cache:
            return 0
        if user_id is not None:
            return self.invalidate_cache_for_user(user_id)
        doc_str = str(document_id)
        removed = 0
        keys = list(self._cache.keys())
        for k in keys:
            # Keys look like: u:<uuid>|q:<query>|d:<doc1,doc2> or d:*
            try:
                dpos = k.rfind("|d:")
                if dpos == -1:
                    continue
                doc_part = k[dpos+3:]
                if doc_part == "*" or doc_str in doc_part.split(","):
                    self._cache.pop(k, None)
                    removed += 1
            except Exception:
                # Don't let key parsing errors block invalidation
                continue
        if removed:
            logger.info(f"RAG cache invalidated due to document {document_id}: {removed} entries removed")
        return removed
    
    async def check_rag_availability(self, user_id: UUID) -> Dict[str, Any]:
        """
        Check if RAG functionality is available for a user.
        
        Args:
            user_id: ID of the user to check
            
        Returns:
            Dictionary with availability status and metadata
        """
        try:
            # Check if user has any documents with vectors
            # For placeholder implementation, always return available
            
            # Get index stats
            index_stats = await vector_store_service.get_index_stats() # type: ignore
            
            return {
                "rag_available": True,
                "user_documents": 0,  # TODO: Count user documents with vectors
                "index_stats": index_stats,
                "embedding_model": "pinecone-integrated"
            }
            
        except Exception as e:
            logger.error(f"Error checking RAG availability: {e}")
            return {
                "rag_available": False,
                "error": str(e)
            }
    
    def get_rag_metadata(self) -> Dict[str, Any]:
        """Get metadata about the RAG configuration."""
        return {
            "max_context_length": self.max_context_length,
            "top_k_retrieval": self.top_k_retrieval,
            "embedding_service": "pinecone-integrated",
            "vector_store": {
                "index_name": vector_store_service.index_name,
                "namespace": vector_store_service.namespace
            }
        }

    async def get_context_for_documents(self, query: str, document_ids: List[UUID]) -> Dict[str, Any]:
        """
        Get RAG context filtered by specific document IDs.
        
        Args:
            query: The user's question/query
            document_ids: List of document UUIDs to filter by
            
        Returns:
            Dictionary containing context and source information
        """
        try:
            logger.info(f"🔍 Getting RAG context for {len(document_ids)} documents")
            
            if not document_ids:
                return {"context": "", "sources": []}
            
            # Convert UUIDs to strings for vector store filtering
            doc_id_strings = [str(doc_id) for doc_id in document_ids]
            
            # Use text-native search directly
            
            # Search for relevant chunks filtered by document IDs
            search_results = await vector_store_service.search_similar_vectors( 
                query_text=query,
                filter_metadata={"document_id": {"$in": doc_id_strings}},
                top_k=self.top_k_retrieval,
            )
            
            if not search_results:
                logger.warning(f"No relevant chunks found for query in selected documents")
                return {"context": "", "sources": []}
            
            # Build context from search results
            context_parts = []
            sources = []
            current_length = 0
            
            for result in search_results:
                chunk_text = result.text or result.metadata.get("text", "")
                source_info = {
                    "document_id": result.metadata.get("document_id"),
                    "chunk_index": result.metadata.get("chunk_index", 0),
                    "score": result.score
                }
                
                # Check if adding this chunk would exceed context length
                if current_length + len(chunk_text) > self.max_context_length:
                    break
                
                context_parts.append(chunk_text)
                sources.append(source_info)
                current_length += len(chunk_text)
            
            context = "\n\n".join(context_parts)
            
            logger.info(f"✅ Built context from {len(context_parts)} chunks, {current_length} chars")
            
            return {
                "context": context,
                "sources": sources,
                "query": query,
                "document_count": len(document_ids),
                "chunk_count": len(context_parts)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting context for documents: {e}")
            return {"context": "", "sources": [], "error": str(e)}


# Create service instance
rag_service = RAGService()
