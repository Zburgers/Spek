"""Document processing service for text extraction and content analysis."""

import base64
import re
from io import BytesIO
from typing import List, Optional

try:
    import pypdf
    from docx import Document as DocxDocument
except ImportError:
    pypdf = None
    DocxDocument = None


class DocumentProcessingError(Exception):
    """Raised when document processing fails."""
    pass


class DocumentProcessor:
    """Service for processing various document types and extracting text content."""

    SUPPORTED_TYPES = {
        "application/pdf": "pdf",
        "text/plain": "txt", 
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc"  # Basic support
    }

    @classmethod
    def is_supported_type(cls, content_type: str) -> bool:
        """Check if the document type is supported for processing."""
        return content_type in cls.SUPPORTED_TYPES

    @classmethod
    def extract_text(cls, content: str, content_type: str, file_name: str = "") -> str:
        """
        Extract text content from various document formats.
        
        Args:
            content: Hex-encoded file content
            content_type: MIME type of the file
            file_name: Original filename for context
            
        Returns:
            Extracted text content
            
        Raises:
            DocumentProcessingError: If processing fails
        """
        try:
            # Convert hex content back to bytes
            file_bytes = bytes.fromhex(content)
            
            if content_type == "text/plain":
                return cls._extract_text_from_txt(file_bytes)
            elif content_type == "application/pdf":
                return cls._extract_text_from_pdf(file_bytes)
            elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                return cls._extract_text_from_docx(file_bytes)
            else:
                raise DocumentProcessingError(f"Unsupported content type: {content_type}")
                
        except Exception as e:
            raise DocumentProcessingError(f"Failed to extract text from {file_name}: {str(e)}")

    @staticmethod
    def _extract_text_from_txt(file_bytes: bytes) -> str:
        """Extract text from plain text files."""
        try:
            # Try UTF-8 first, fallback to latin-1
            try:
                return file_bytes.decode('utf-8')
            except UnicodeDecodeError:
                return file_bytes.decode('latin-1', errors='ignore')
        except Exception as e:
            raise DocumentProcessingError(f"Failed to decode text file: {str(e)}")

    @staticmethod 
    def _extract_text_from_pdf(file_bytes: bytes) -> str:
        """Extract text from PDF files using pypdf."""
        if pypdf is None:
            raise DocumentProcessingError("pypdf not available - cannot process PDF files")
            
        try:
            pdf_stream = BytesIO(file_bytes)
            reader = pypdf.PdfReader(pdf_stream)
            
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text.strip():
                    text_parts.append(page_text)
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            raise DocumentProcessingError(f"Failed to extract text from PDF: {str(e)}")

    @staticmethod
    def _extract_text_from_docx(file_bytes: bytes) -> str:
        """Extract text from DOCX files using python-docx."""
        if DocxDocument is None:
            raise DocumentProcessingError("python-docx not available - cannot process DOCX files")
            
        try:
            docx_stream = BytesIO(file_bytes)
            document = DocxDocument(docx_stream)
            
            text_parts = []
            for paragraph in document.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            raise DocumentProcessingError(f"Failed to extract text from DOCX: {str(e)}")

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""
            
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?;:()-]', ' ', text)
        
        # Remove excessive spaces again
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """
        Split text into overlapping chunks for processing.
        
        Args:
            text: Input text to chunk
            chunk_size: Maximum characters per chunk
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of text chunks
        """
        if not text or len(text) <= chunk_size:
            return [text] if text else []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at word boundaries
            if end < len(text):
                # Look for sentence or paragraph breaks first
                next_break = text.find('\n\n', start + chunk_size - overlap, end)
                if next_break == -1:
                    next_break = text.find('.', start + chunk_size - overlap, end)
                if next_break == -1:
                    next_break = text.find(' ', start + chunk_size - overlap, end)
                
                if next_break != -1 and next_break > start:
                    end = next_break + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = max(end - overlap, start + 1)
            
        return chunks