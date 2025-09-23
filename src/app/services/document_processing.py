"""
Document Processing Service

Handles text extraction and chunking for RAG pipeline.
This service extracts clean text from various document formats and splits it into chunks.
"""

import re
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging
import io

from ..core.config import settings

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a chunk of text from a document."""
    
    def __init__(self, text: str, chunk_index: int, metadata: Optional[Dict[str, Any]] = None):
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
    
    async def extract_text_from_content(self, content: str, file_type: str, file_name: Optional[str] = None) -> str:
        """
        Extract text from document content based on file type.
        
        Args:
            content: Base64 encoded or raw file content
            file_type: MIME type of the file
            file_name: Optional original file name to infer extension
            
        Returns:
            Extracted plain text
        """
        try:
            # Detect and decode storage format: current API stores hex-encoded bytes
            raw_bytes: Optional[bytes] = None
            decoded_as_hex = False
            try:
                raw_bytes = bytes.fromhex(content)
                decoded_as_hex = True
                logger.info(f"Extraction: decoded content as hex, size={len(raw_bytes)} bytes")
            except ValueError:
                # Not hex; treat content as plain text string bytes
                raw_bytes = content.encode("utf-8", errors="ignore")
                logger.info("Extraction: content was not hex; treated as raw UTF-8 text")

            mime = (file_type or "").lower()
            ext = (file_name.split(".")[-1].lower() if file_name and "." in file_name else "")

            # Text files
            if mime.startswith("text/") or ext == "txt":
                try:
                    text = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw_bytes.decode("latin-1", errors="ignore")
                return self._clean_text(text)

            # PDF files
            if mime == "application/pdf" or ext == "pdf":
                try:
                    # Prefer pypdf for robustness
                    try:
                        from pypdf import PdfReader  # type: ignore
                        reader = PdfReader(io.BytesIO(raw_bytes))
                        pages_text = []
                        for i, page in enumerate(reader.pages):
                            try:
                                pages_text.append(page.extract_text() or "")
                            except Exception as page_err:
                                logger.warning(f"PDF extract warning on page {i}: {page_err}")
                        text = "\n".join(pages_text)
                    except Exception as pypdf_err:
                        logger.warning(f"pypdf failed ({type(pypdf_err).__name__}): {pypdf_err}; trying pdfminer.six")
                        try:
                            from pdfminer.high_level import extract_text  # type: ignore
                            text = extract_text(io.BytesIO(raw_bytes))
                        except Exception as pdfminer_err:
                            logger.error(f"Both pypdf and pdfminer failed: {pdfminer_err}")
                            raise
                    return self._clean_text(text)
                except Exception as e:
                    logger.error(f"Error extracting PDF text: {e}")
                    raise

            # DOCX files
            if (
                mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                or ext == "docx"
            ): 
                try:
                    try:
                        import docx  # type: ignore
                    except Exception as import_err:
                        logger.error(f"python-docx not installed: {import_err}")
                        raise
                    doc = docx.Document(io.BytesIO(raw_bytes))
                    text = "\n".join([p.text for p in doc.paragraphs])
                    return self._clean_text(text)
                except Exception as e:
                    logger.error(f"Error extracting DOCX text: {e}")
                    raise

            # Fallback: best-effort decode as text
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = raw_bytes.decode("latin-1", errors="ignore")
            return self._clean_text(text)

        except Exception as e:
            logger.error(f"Error extracting text from {file_type} ({file_name}): {e}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters that might interfere
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', '', text)
        return text.strip()
    
    async def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
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
            content: Raw document content (hex string or text)
            file_type: MIME type of the document
            file_name: Original filename
        
        Returns:
            List of processed chunks ready for embedding
        """
        logger.info(
            f"Processing document {document_id} ({file_name}) with chunk_size={self.chunk_size}, overlap={self.chunk_overlap}"
        )

        # Extract text
        extracted_text = await self.extract_text_from_content(content, file_type, file_name)
        if not extracted_text:
            logger.warning(f"No text extracted from document {document_id}")
            return []

        # Create metadata
        metadata = {
            "document_id": str(document_id),
            "file_name": file_name,
            "file_type": file_type,
            "original_length": len(extracted_text),
        }

        # Chunk the text
        chunks = await self.chunk_text(extracted_text, metadata)

        logger.info(
            f"Successfully processed document {document_id} into {len(chunks)} chunks"
        )
        return chunks


# Create service instance using settings
document_processing_service = DocumentProcessingService(
    chunk_size=int(getattr(settings, "CHUNK_SIZE", 1000)),
    chunk_overlap=int(getattr(settings, "CHUNK_OVERLAP", 200)),
)
