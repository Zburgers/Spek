"""RAG (Retrieval-Augmented Generation) service for document querying."""

import re
from typing import List, Optional, Tuple
from datetime import datetime

from google import genai
from google.genai import types

from ..core.config import settings
from .document_processor import DocumentProcessor


class RAGError(Exception):
    """Raised when RAG processing fails."""
    pass


class DocumentChunk:
    """Represents a chunk of document text with metadata."""
    
    def __init__(self, text: str, chunk_index: int, source_info: str):
        self.text = text
        self.chunk_index = chunk_index  
        self.source_info = source_info
        self.relevance_score: float = 0.0


class RAGService:
    """Service for performing RAG queries on documents."""
    
    def __init__(self):
        """Initialize the RAG service with Gemini client."""
        try:
            api_key = settings.API_KEY
            if not api_key:
                raise RAGError("AI_API_KEY not configured")
            
            self.client = genai.Client(api_key=api_key.get_secret_value())
            self.model_name = "gemini-2.0-flash-001"
            
        except Exception as e:
            raise RAGError(f"Failed to initialize RAG service: {str(e)}")

    async def query_document(
        self, 
        query: str, 
        document_content: str, 
        document_name: str,
        max_chunks: int = 5
    ) -> Tuple[str, List[DocumentChunk], float]:
        """
        Query a document using RAG approach.
        
        Args:
            query: User's query
            document_content: Hex-encoded document content
            document_name: Name of the document
            max_chunks: Maximum number of chunks to consider
            
        Returns:
            Tuple of (answer, relevant_chunks, confidence_score)
        """
        try:
            # Extract and process document text
            # For now, we'll assume it's plain text. In a real implementation,
            # we'd determine the content type and extract accordingly
            try:
                # Try to decode as plain text first
                text = bytes.fromhex(document_content).decode('utf-8', errors='ignore')
            except:
                # Fallback to treating as already decoded text
                text = document_content
            
            # Clean and chunk the text
            clean_text = DocumentProcessor.clean_text(text)
            chunks = DocumentProcessor.chunk_text(clean_text, chunk_size=800, overlap=100)
            
            if not chunks:
                return "No readable content found in the document.", [], 0.0
            
            # Find most relevant chunks
            relevant_chunks = await self._find_relevant_chunks(query, chunks, document_name, max_chunks)
            
            if not relevant_chunks:
                return "No relevant content found for your query.", [], 0.0
            
            # Generate answer using relevant chunks
            answer, confidence = await self._generate_answer(query, relevant_chunks, document_name)
            
            return answer, relevant_chunks, confidence
            
        except Exception as e:
            raise RAGError(f"Failed to query document: {str(e)}")

    async def _find_relevant_chunks(
        self, 
        query: str, 
        chunks: List[str], 
        document_name: str,
        max_chunks: int
    ) -> List[DocumentChunk]:
        """
        Find the most relevant chunks for the query using semantic similarity.
        
        For now, this uses simple keyword matching. In a production system,
        you'd use embeddings for semantic similarity.
        """
        try:
            query_terms = set(query.lower().split())
            chunk_objects = []
            
            for i, chunk in enumerate(chunks):
                # Simple relevance scoring based on keyword overlap
                chunk_terms = set(chunk.lower().split())
                overlap = len(query_terms.intersection(chunk_terms))
                relevance_score = overlap / len(query_terms) if query_terms else 0
                
                # Boost score for exact phrase matches
                if query.lower() in chunk.lower():
                    relevance_score += 0.5
                
                chunk_obj = DocumentChunk(chunk, i, document_name)
                chunk_obj.relevance_score = relevance_score
                chunk_objects.append(chunk_obj)
            
            # Sort by relevance and take top chunks
            chunk_objects.sort(key=lambda x: x.relevance_score, reverse=True)
            
            # Only return chunks with some relevance
            relevant_chunks = [c for c in chunk_objects[:max_chunks] if c.relevance_score > 0]
            
            return relevant_chunks
            
        except Exception as e:
            raise RAGError(f"Failed to find relevant chunks: {str(e)}")

    async def _generate_answer(
        self, 
        query: str, 
        relevant_chunks: List[DocumentChunk],
        document_name: str
    ) -> Tuple[str, float]:
        """Generate an answer using the relevant chunks and Gemini AI."""
        try:
            # Prepare context from relevant chunks
            context_parts = []
            for chunk in relevant_chunks:
                context_parts.append(f"[Excerpt {chunk.chunk_index + 1}]: {chunk.text}")
            
            context = "\n\n".join(context_parts)
            
            # Create the prompt for Gemini
            prompt = f"""You are a helpful assistant that answers questions based on provided document content. 

Document: {document_name}

Context from document:
{context}

Question: {query}

Instructions:
- Answer the question based ONLY on the provided context
- If the context doesn't contain enough information to answer the question, say so
- Be specific and cite which excerpt(s) support your answer
- Keep your answer concise but complete
- If you're uncertain, indicate your level of confidence

Answer:"""

            # Generate response using Gemini
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[types.UserContent(
                    parts=[types.Part.from_text(text=prompt)]
                )],
                config=types.GenerateContentConfig(
                    temperature=0.3,  # Lower temperature for more factual responses
                    max_output_tokens=1024,
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                )
            )
            
            answer = response.text.strip()
            
            # Calculate confidence based on relevance scores and response characteristics
            avg_relevance = sum(c.relevance_score for c in relevant_chunks) / len(relevant_chunks)
            
            # Simple confidence heuristic
            confidence = min(0.95, avg_relevance * 0.8 + 0.2)
            
            # Lower confidence if the answer indicates uncertainty
            uncertainty_indicators = [
                "i don't know", "not enough information", "unclear", 
                "cannot determine", "insufficient", "not provided"
            ]
            if any(indicator in answer.lower() for indicator in uncertainty_indicators):
                confidence *= 0.6
            
            return answer, confidence
            
        except Exception as e:
            raise RAGError(f"Failed to generate answer: {str(e)}")

    def process_uploaded_document(
        self, 
        content: str, 
        content_type: str, 
        file_name: str
    ) -> Tuple[str, str]:
        """
        Process an uploaded document and extract its text content.
        
        Args:
            content: Hex-encoded file content
            content_type: MIME type of the file  
            file_name: Original filename
            
        Returns:
            Tuple of (extracted_text, status)
        """
        try:
            if not DocumentProcessor.is_supported_type(content_type):
                return "", "unsupported_type"
            
            extracted_text = DocumentProcessor.extract_text(content, content_type, file_name)
            
            if not extracted_text.strip():
                return "", "no_text_found"
            
            cleaned_text = DocumentProcessor.clean_text(extracted_text)
            return cleaned_text, "processed"
            
        except Exception as e:
            print(f"Document processing error: {str(e)}")
            return "", "processing_error"