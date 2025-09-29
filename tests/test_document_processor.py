"""Tests for document processing functionality."""

import pytest
from unittest.mock import Mock, patch
from src.app.services.document_processor import DocumentProcessor, DocumentProcessingError


class TestDocumentProcessor:
    """Test document processing functionality."""
    
    def test_is_supported_type(self):
        """Test document type support checking."""
        assert DocumentProcessor.is_supported_type("text/plain")
        assert DocumentProcessor.is_supported_type("application/pdf")
        assert DocumentProcessor.is_supported_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert not DocumentProcessor.is_supported_type("image/jpeg")
        assert not DocumentProcessor.is_supported_type("application/unknown")
    
    def test_extract_text_from_txt(self):
        """Test text extraction from plain text files."""
        test_text = "Hello, this is a test document."
        hex_content = test_text.encode('utf-8').hex()
        
        result = DocumentProcessor.extract_text(hex_content, "text/plain", "test.txt")
        assert result == test_text
    
    def test_extract_text_from_txt_with_encoding_issues(self):
        """Test text extraction with encoding issues."""
        # Create text with some non-UTF8 bytes
        test_bytes = b"Hello \xff\xfe test"
        hex_content = test_bytes.hex()
        
        result = DocumentProcessor.extract_text(hex_content, "text/plain", "test.txt")
        # Should handle encoding errors gracefully
        assert "Hello" in result
        assert "test" in result
    
    def test_extract_text_unsupported_type(self):
        """Test handling of unsupported document types."""
        hex_content = "deadbeef"
        
        with pytest.raises(DocumentProcessingError):
            DocumentProcessor.extract_text(hex_content, "image/jpeg", "test.jpg")
    
    def test_clean_text(self):
        """Test text cleaning functionality."""
        dirty_text = "This  is    a   test\n\n\nwith   lots  of   whitespace!!!"
        clean_text = DocumentProcessor.clean_text(dirty_text)
        
        # Should normalize whitespace
        assert "  " not in clean_text
        assert "\n\n" not in clean_text
        assert clean_text.strip() == clean_text
    
    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        text = "This is a test. " * 100  # Create long text
        chunks = DocumentProcessor.chunk_text(text, chunk_size=200, overlap=50)
        
        assert len(chunks) > 1  # Should create multiple chunks
        assert all(len(chunk) <= 200 for chunk in chunks)  # Respect chunk size
        assert len(chunks[0]) > 0  # Chunks should not be empty
    
    def test_chunk_text_short_text(self):
        """Test chunking of short text."""
        short_text = "This is a short text."
        chunks = DocumentProcessor.chunk_text(short_text, chunk_size=1000)
        
        assert len(chunks) == 1
        assert chunks[0] == short_text
    
    def test_chunk_text_empty_text(self):
        """Test chunking of empty text."""
        chunks = DocumentProcessor.chunk_text("", chunk_size=1000)
        assert chunks == []
        
        chunks = DocumentProcessor.chunk_text(None, chunk_size=1000)
        assert chunks == []
    
    @patch('src.app.services.document_processor.pypdf')
    def test_extract_text_from_pdf_not_available(self, mock_pypdf):
        """Test PDF extraction when pypdf is not available."""
        mock_pypdf.__bool__ = Mock(return_value=False)
        mock_pypdf.PdfReader = None
        
        hex_content = "deadbeef"
        
        with pytest.raises(DocumentProcessingError, match="pypdf not available"):
            DocumentProcessor.extract_text(hex_content, "application/pdf", "test.pdf")
    
    @patch('src.app.services.document_processor.DocxDocument')
    def test_extract_text_from_docx_not_available(self, mock_docx):
        """Test DOCX extraction when python-docx is not available."""
        mock_docx.__bool__ = Mock(return_value=False)
        mock_docx = None
        
        hex_content = "deadbeef"
        
        with pytest.raises(DocumentProcessingError, match="python-docx not available"):
            DocumentProcessor.extract_text(hex_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "test.docx")


if __name__ == "__main__":
    pytest.main([__file__])