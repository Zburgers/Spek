"""
RAG (Retrieval-Augmented Generation) Service

Orchestrates the RAG pipeline by coordinating retrieval and generation components.
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from .embedding import embedding_service
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
    
    def __init__(self, max_context_length: int = 4000, top_k_retrieval: int = 5):
        """
        Initialize the RAG service.
        
        Args:
            max_context_length: Maximum character length for context
            top_k_retrieval: Number of top similar chunks to retrieve
        """
        self.max_context_length = max_context_length
        self.top_k_retrieval = top_k_retrieval
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
            logger.info(f"Retrieving context for query: '{query[:50]}...'")
            
            # Step 1: Generate query embedding
            query_embedding = await embedding_service.get_query_embedding(query)
            
            # Step 2: Prepare metadata filters
            filter_metadata = {"user_id": str(user_id)}
            if document_ids:
                logger.info(f"Filtering RAG context by {len(document_ids)} document(s).")
                filter_metadata["document_id"] = {"$in": [str(d) for d in document_ids]}
            
            # Step 3: Search for similar vectors
            similar_chunks = await vector_store_service.search_similar_vectors(
                query_vector=query_embedding,
                top_k=self.top_k_retrieval,
                filter_metadata=filter_metadata
            )
            
            # Step 4: Format context from retrieved chunks
            context = self._format_context(similar_chunks)
            
            # Step 5: Create augmented prompt
            augmented_prompt = self._create_augmented_prompt(query, context)
            
            # Step 6: Prepare metadata
            metadata = {
                "chunks_retrieved": len(similar_chunks),
                "context_length": len(context),
                "query_length": len(query),
                "user_id": str(user_id),
                "document_filter": [str(d) for d in document_ids] if document_ids else None
            }
            
            logger.info(f"Retrieved {len(similar_chunks)} chunks, context length: {len(context)}")
            
            return RAGResult(
                retrieved_chunks=similar_chunks,
                context=context,
                augmented_prompt=augmented_prompt,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error in retrieve_context: {e}")
            raise
    
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
            index_stats = await vector_store_service.get_index_stats()
            
            return {
                "rag_available": True,
                "user_documents": 0,  # TODO: Count user documents with vectors
                "index_stats": index_stats,
                "embedding_model": embedding_service.get_embedding_metadata()
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
            "embedding_service": embedding_service.get_embedding_metadata(),
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
            
            # Generate embedding for the query
            query_embedding = await embedding_service.generate_embedding(query)
            
            # Search for relevant chunks filtered by document IDs
            search_results = await vector_store_service.search_similar(
                embedding=query_embedding,
                filter_metadata={"document_id": {"$in": doc_id_strings}},
                top_k=self.top_k_retrieval
            )
            
            if not search_results:
                logger.warning(f"No relevant chunks found for query in selected documents")
                return {"context": "", "sources": []}
            
            # Build context from search results
            context_parts = []
            sources = []
            current_length = 0
            
            for result in search_results:
                chunk_text = result.metadata.get("text", "")
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
