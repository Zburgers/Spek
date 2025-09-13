"""
Document Processing Service

Handles text extraction and chunking for RAG pipeline.
This service extracts clean text from various document formats and splits it into chunks.
"""

import re
from typing import List, Dict, Any
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a chunk of text from a document."""
    
    def __init__(self, text: str, chunk_index: int, metadata: Dict[str, Any] = None):
        self.text = text
        self.chunk_index = chunk_index
        self.metadata = metadata or {}


class DocumentProcessingService:
    """Service for processing documents into chunks suitable for RAG."""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize the document processing service.
        
        Args:
            chunk_size: Maximum number of characters per chunk
            chunk_overlap: Number of characters to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    async def extract_text_from_content(self, content: str, file_type: str) -> str:
        """
        Extract text from document content based on file type.
        
        Args:
            content: Base64 encoded or raw file content
            file_type: MIME type of the file
            
        Returns:
            Extracted plain text
        """
        try:
            # For now, handle text files and simple formats
            # TODO: Add proper document parsing (PDF, DOCX, etc.)
            
            if file_type.startswith('text/'):
                # Handle text files - decode from hex if needed
                try:
                    # Try to decode from hex (as stored in current implementation)
                    decoded_bytes = bytes.fromhex(content)
                    text = decoded_bytes.decode('utf-8')
                except (ValueError, UnicodeDecodeError):
                    # If hex decode fails, treat as plain text
                    text = content
            else:
                # For other file types, return placeholder for now
                # TODO: Implement PDF, DOCX, etc. parsing
                text = f"[Content from {file_type} file - parsing not yet implemented]"
                
            return self._clean_text(text)
            
        except Exception as e:
            logger.error(f"Error extracting text from {file_type}: {e}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters that might interfere
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', '', text)
        return text.strip()
    
    async def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[DocumentChunk]:
        """
        Split text into overlapping chunks for better retrieval.
        
        Args:
            text: The text to chunk
            metadata: Additional metadata to attach to chunks
            
        Returns:
            List of DocumentChunk objects
        """
        if not text:
            return []
        
        chunks = []
        chunk_index = 0
        
        # Simple sentence-aware chunking
        sentences = self._split_into_sentences(text)
        current_chunk = ""
        
        for sentence in sentences:
            # Check if adding this sentence would exceed chunk size
            if len(current_chunk + " " + sentence) > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_metadata = {**(metadata or {}), "chunk_index": chunk_index}
                chunks.append(DocumentChunk(current_chunk.strip(), chunk_index, chunk_metadata))
                
                # Start new chunk with overlap
                current_chunk = self._get_overlap_text(current_chunk) + " " + sentence
                chunk_index += 1
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        # Add the last chunk if it has content
        if current_chunk.strip():
            chunk_metadata = {**(metadata or {}), "chunk_index": chunk_index}
            chunks.append(DocumentChunk(current_chunk.strip(), chunk_index, chunk_metadata))
        
        logger.info(f"Created {len(chunks)} chunks from text of length {len(text)}")
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for better chunking."""
        # Simple sentence splitting - can be improved with nltk or spacy
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _get_overlap_text(self, text: str) -> str:
        """Get the last portion of text for chunk overlap."""
        if len(text) <= self.chunk_overlap:
            return text
        
        # Try to find a good break point (word boundary)
        overlap_text = text[-self.chunk_overlap:]
        words = overlap_text.split()
        if len(words) > 1:
            # Remove the first partial word to ensure clean overlap
            return ' '.join(words[1:])
        return overlap_text
    
    async def process_document(self, document_id: UUID, content: str, file_type: str, 
                             file_name: str) -> List[DocumentChunk]:
        """
        Full document processing pipeline.
        
        Args:
            document_id: UUID of the document
            content: Raw document content
            file_type: MIME type of the document
            file_name: Original filename
            
        Returns:
            List of processed chunks ready for embedding
        """
        logger.info(f"Processing document {document_id} ({file_name})")
        
        # Extract text
        extracted_text = await self.extract_text_from_content(content, file_type)
        
        # Create metadata
        metadata = {
            "document_id": str(document_id),
            "file_name": file_name,
            "file_type": file_type,
            "original_length": len(extracted_text)
        }
        
        # Chunk the text
        chunks = await self.chunk_text(extracted_text, metadata)
        
        logger.info(f"Successfully processed document {document_id} into {len(chunks)} chunks")
        return chunks


# Create service instance
document_processing_service = DocumentProcessingService()
