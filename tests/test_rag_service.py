"""Tests for RAG service functionality."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.app.services.rag_service import RAGService, RAGError, DocumentChunk


class TestRAGService:
    """Test RAG service functionality."""
    
    @patch('src.app.services.rag_service.settings')
    @patch('src.app.services.rag_service.genai.Client')
    def test_init_success(self, mock_client, mock_settings):
        """Test successful RAG service initialization."""
        mock_api_key = Mock()
        mock_api_key.get_secret_value.return_value = "test-api-key"
        mock_settings.API_KEY = mock_api_key
        
        service = RAGService()
        assert service.client is not None
        assert service.model_name == "gemini-2.0-flash-001"
    
    @patch('src.app.services.rag_service.settings')
    def test_init_no_api_key(self, mock_settings):
        """Test RAG service initialization without API key."""
        mock_settings.API_KEY = None
        
        with pytest.raises(RAGError, match="AI_API_KEY not configured"):
            RAGService()
    
    def test_document_chunk(self):
        """Test DocumentChunk class."""
        chunk = DocumentChunk("test text", 0, "test.txt")
        assert chunk.text == "test text"
        assert chunk.chunk_index == 0
        assert chunk.source_info == "test.txt"
        assert chunk.relevance_score == 0.0
    
    @patch('src.app.services.rag_service.settings')
    @patch('src.app.services.rag_service.genai.Client')
    async def test_find_relevant_chunks(self, mock_client, mock_settings):
        """Test finding relevant chunks."""
        mock_api_key = Mock()
        mock_api_key.get_secret_value.return_value = "test-api-key"
        mock_settings.API_KEY = mock_api_key
        
        service = RAGService()
        
        chunks = [
            "This is about cats and dogs.",
            "Python programming is great.",
            "Machine learning with cats is interesting.",
            "Dogs are loyal pets."
        ]
        
        relevant = await service._find_relevant_chunks("cats", chunks, "test.txt", 3)
        
        # Should find chunks mentioning cats
        assert len(relevant) > 0
        assert any("cats" in chunk.text.lower() for chunk in relevant)
        
        # Should be sorted by relevance
        if len(relevant) > 1:
            assert relevant[0].relevance_score >= relevant[1].relevance_score
    
    @patch('src.app.services.rag_service.settings')
    @patch('src.app.services.rag_service.genai.Client')
    async def test_find_relevant_chunks_no_matches(self, mock_client, mock_settings):
        """Test finding relevant chunks with no matches."""
        mock_api_key = Mock()
        mock_api_key.get_secret_value.return_value = "test-api-key"
        mock_settings.API_KEY = mock_api_key
        
        service = RAGService()
        
        chunks = ["This is about cars.", "Programming in Java."]
        relevant = await service._find_relevant_chunks("quantum physics", chunks, "test.txt", 3)
        
        # Should return empty list when no relevant chunks found
        assert len(relevant) == 0
    
    @patch('src.app.services.rag_service.settings')
    @patch('src.app.services.rag_service.genai.Client')
    async def test_generate_answer(self, mock_client, mock_settings):
        """Test answer generation."""
        mock_api_key = Mock()
        mock_api_key.get_secret_value.return_value = "test-api-key"
        mock_settings.API_KEY = mock_api_key
        
        # Mock the Gemini API response
        mock_response = Mock()
        mock_response.text = "Based on the provided context, cats are mentioned as pets."
        mock_client.return_value.models.generate_content.return_value = mock_response
        
        service = RAGService()
        
        chunks = [
            DocumentChunk("Cats are great pets.", 0, "test.txt"),
            DocumentChunk("Dogs are loyal companions.", 1, "test.txt")
        ]
        for chunk in chunks:
            chunk.relevance_score = 0.8
        
        answer, confidence = await service._generate_answer("What pets are mentioned?", chunks, "test.txt")
        
        assert answer == "Based on the provided context, cats are mentioned as pets."
        assert 0 < confidence <= 1
    
    @patch('src.app.services.rag_service.settings')
    @patch('src.app.services.rag_service.genai.Client')
    async def test_generate_answer_uncertain(self, mock_client, mock_settings):
        """Test answer generation with uncertain response."""
        mock_api_key = Mock()
        mock_api_key.get_secret_value.return_value = "test-api-key"
        mock_settings.API_KEY = mock_api_key
        
        # Mock uncertain response
        mock_response = Mock()
        mock_response.text = "I don't have enough information to answer that question."
        mock_client.return_value.models.generate_content.return_value = mock_response
        
        service = RAGService()
        
        chunks = [DocumentChunk("Some unrelated text.", 0, "test.txt")]
        chunks[0].relevance_score = 0.1
        
        answer, confidence = await service._generate_answer("What is the meaning of life?", chunks, "test.txt")
        
        assert "don't have enough information" in answer
        assert confidence < 0.5  # Should have lower confidence for uncertain answers
    
    @patch('src.app.services.rag_service.DocumentProcessor')
    @patch('src.app.services.rag_service.settings')
    @patch('src.app.services.rag_service.genai.Client')
    def test_process_uploaded_document_success(self, mock_client, mock_settings, mock_processor):
        """Test successful document processing."""
        mock_api_key = Mock()
        mock_api_key.get_secret_value.return_value = "test-api-key"
        mock_settings.API_KEY = mock_api_key
        
        mock_processor.is_supported_type.return_value = True
        mock_processor.extract_text.return_value = "Extracted text content"
        mock_processor.clean_text.return_value = "Clean text content"
        
        service = RAGService()
        
        text, status = service.process_uploaded_document(
            "48656c6c6f",  # "Hello" in hex
            "text/plain",
            "test.txt"
        )
        
        assert text == "Clean text content"
        assert status == "processed"
    
    @patch('src.app.services.rag_service.DocumentProcessor')
    @patch('src.app.services.rag_service.settings')
    @patch('src.app.services.rag_service.genai.Client')
    def test_process_uploaded_document_unsupported(self, mock_client, mock_settings, mock_processor):
        """Test processing unsupported document type."""
        mock_api_key = Mock()
        mock_api_key.get_secret_value.return_value = "test-api-key"
        mock_settings.API_KEY = mock_api_key
        
        mock_processor.is_supported_type.return_value = False
        
        service = RAGService()
        
        text, status = service.process_uploaded_document(
            "deadbeef",
            "image/jpeg",
            "test.jpg"
        )
        
        assert text == ""
        assert status == "unsupported_type"
    
    @patch('src.app.services.rag_service.DocumentProcessor')
    @patch('src.app.services.rag_service.settings')
    @patch('src.app.services.rag_service.genai.Client')
    def test_process_uploaded_document_error(self, mock_client, mock_settings, mock_processor):
        """Test document processing with error."""
        mock_api_key = Mock()
        mock_api_key.get_secret_value.return_value = "test-api-key"
        mock_settings.API_KEY = mock_api_key
        
        mock_processor.is_supported_type.return_value = True
        mock_processor.extract_text.side_effect = Exception("Processing failed")
        
        service = RAGService()
        
        text, status = service.process_uploaded_document(
            "48656c6c6f",
            "text/plain",
            "test.txt"
        )
        
        assert text == ""
        assert status == "processing_error"


if __name__ == "__main__":
    pytest.main([__file__])