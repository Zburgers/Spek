"""
Integration tests for the centralized document management system.
Tests both backend API endpoints and the complete workflow.
"""

import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status
import json
import io
from unittest.mock import patch, MagicMock

from app.models.document import Document
from app.models.chat import Chat
from app.models.chat_document import ChatDocument
from app.crud.crud_document import document_crud
from app.crud.crud_chat import chat_crud
from app.crud.crud_chat_document import chat_document_crud


class TestDocumentManagementIntegration:
    """Test suite for centralized document management system"""

    @pytest.fixture
    async def test_documents(self, async_session: AsyncSession, test_user):
        """Create test documents with different scopes"""
        documents = []
        
        # App-wide document
        app_doc = await document_crud.create(
            async_session,
            obj_in={
                "filename": "app_document.pdf",
                "file_size": 1024000,
                "content_type": "application/pdf",
                "scope": "app_wide",
                "status": "completed",
                "content": "This is app-wide content for testing",
                "vector_id": "app_vec_123"
            },
            user_id=test_user.uuid
        )
        documents.append(app_doc)
        
        # Chat-specific document
        chat_doc = await document_crud.create(
            async_session,
            obj_in={
                "filename": "chat_document.txt",
                "file_size": 512000,
                "content_type": "text/plain",
                "scope": "chat_specific",
                "status": "completed",
                "content": "This is chat-specific content for testing",
                "vector_id": "chat_vec_456"
            },
            user_id=test_user.uuid
        )
        documents.append(chat_doc)
        
        # Processing document
        proc_doc = await document_crud.create(
            async_session,
            obj_in={
                "filename": "processing_doc.docx",
                "file_size": 2048000,
                "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "scope": "app_wide",
                "status": "processing",
                "content": None,
                "vector_id": None
            },
            user_id=test_user.uuid
        )
        documents.append(proc_doc)
        
        await async_session.commit()
        return documents

    @pytest.fixture
    async def test_chat(self, async_session: AsyncSession, test_user):
        """Create a test chat session"""
        chat = await chat_crud.create(
            async_session,
            obj_in={
                "title": "Test Chat Session",
                "context": "Testing centralized document management"
            },
            user_id=test_user.uuid
        )
        await async_session.commit()
        return chat

    async def test_get_documents_endpoint(self, async_client: AsyncClient, test_user_token, test_documents):
        """Test the enhanced get documents endpoint"""
        response = await async_client.get(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should return paginated results with documents
        assert "data" in data
        assert "count" in data
        assert "has_more" in data
        assert "page" in data
        assert "per_page" in data
        
        documents = data["data"]
        assert len(documents) == 3
        
        # Verify documents have required fields
        for doc in documents:
            assert "uuid" in doc
            assert "filename" in doc
            assert "file_size" in doc
            assert "scope" in doc
            assert "status" in doc
            assert doc["scope"] in ["app_wide", "chat_specific"]

    async def test_get_documents_with_scope_filter(self, async_client: AsyncClient, test_user_token, test_documents):
        """Test filtering documents by scope"""
        # Test app_wide filter
        response = await async_client.get(
            "/api/v1/documents/?scope=app_wide",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        app_docs = data["data"]
        
        assert len(app_docs) == 2  # app_document.pdf and processing_doc.docx
        for doc in app_docs:
            assert doc["scope"] == "app_wide"
        
        # Test chat_specific filter
        response = await async_client.get(
            "/api/v1/documents/?scope=chat_specific",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        chat_docs = data["data"]
        
        assert len(chat_docs) == 1  # chat_document.txt
        assert chat_docs[0]["scope"] == "chat_specific"

    async def test_get_documents_with_status_filter(self, async_client: AsyncClient, test_user_token, test_documents):
        """Test filtering documents by status"""
        response = await async_client.get(
            "/api/v1/documents/?status=completed",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        completed_docs = data["data"]
        
        assert len(completed_docs) == 2
        for doc in completed_docs:
            assert doc["status"] == "completed"

    async def test_upload_document_app_wide(self, async_client: AsyncClient, test_user_token):
        """Test uploading an app-wide document"""
        file_content = b"This is test content for app-wide document"
        
        with patch('app.services.rag_service.RAGService.process_document') as mock_process:
            mock_process.return_value = {"vector_id": "test_vector_123", "chunks": 5}
            
            response = await async_client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {test_user_token}"},
                files={"file": ("test_app.txt", io.BytesIO(file_content), "text/plain")},
                data={"scope": "app_wide"}
            )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["filename"] == "test_app.txt"
        assert data["scope"] == "app_wide"
        assert data["status"] in ["processing", "completed"]
        assert "uuid" in data

    async def test_upload_document_chat_specific(self, async_client: AsyncClient, test_user_token):
        """Test uploading a chat-specific document"""
        file_content = b"This is test content for chat-specific document"
        
        with patch('app.services.rag_service.RAGService.process_document') as mock_process:
            mock_process.return_value = {"vector_id": "test_vector_456", "chunks": 3}
            
            response = await async_client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {test_user_token}"},
                files={"file": ("test_chat.txt", io.BytesIO(file_content), "text/plain")},
                data={"scope": "chat_specific"}
            )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["filename"] == "test_chat.txt"
        assert data["scope"] == "chat_specific"

    async def test_associate_documents_with_chat(self, async_client: AsyncClient, test_user_token, test_documents, test_chat):
        """Test associating multiple documents with a chat"""
        doc_ids = [str(doc.uuid) for doc in test_documents[:2]]  # First two documents
        
        response = await async_client.post(
            f"/api/v1/chats/{test_chat.uuid}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"document_ids": doc_ids}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "associations_created" in data
        assert data["associations_created"] == 2
        assert "chat_id" in data
        assert data["chat_id"] == str(test_chat.uuid)

    async def test_associate_single_document_with_chat(self, async_client: AsyncClient, test_user_token, test_documents, test_chat):
        """Test associating a single document with a chat (backward compatibility)"""
        doc_id = str(test_documents[2].uuid)  # Third document
        
        response = await async_client.post(
            f"/api/v1/chats/{test_chat.uuid}/documents/{doc_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["message"] == "Document associated with chat successfully"
        assert "association" in data
        assert data["association"]["document_id"] == doc_id

    async def test_get_chat_documents(self, async_client: AsyncClient, test_user_token, test_documents, test_chat, async_session):
        """Test getting documents associated with a chat"""
        # First associate some documents
        doc_ids = [str(doc.uuid) for doc in test_documents[:2]]
        
        await async_client.post(
            f"/api/v1/chats/{test_chat.uuid}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"document_ids": doc_ids}
        )
        
        # Now get the chat documents
        response = await async_client.get(
            f"/api/v1/chats/{test_chat.uuid}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) == 2
        for doc in data:
            assert "uuid" in doc
            assert "filename" in doc
            assert "scope" in doc
            assert doc["uuid"] in doc_ids

    async def test_remove_document_from_chat(self, async_client: AsyncClient, test_user_token, test_documents, test_chat):
        """Test removing a document from a chat"""
        # First associate a document
        doc_id = str(test_documents[0].uuid)
        
        await async_client.post(
            f"/api/v1/chats/{test_chat.uuid}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"document_ids": [doc_id]}
        )
        
        # Now remove it
        response = await async_client.delete(
            f"/api/v1/chats/{test_chat.uuid}/documents/{doc_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["message"] == "Document removed from chat successfully"

    async def test_delete_document(self, async_client: AsyncClient, test_user_token, test_documents):
        """Test deleting a document"""
        doc_id = str(test_documents[0].uuid)
        
        with patch('app.services.rag_service.RAGService.delete_document') as mock_delete:
            mock_delete.return_value = True
            
            response = await async_client.delete(
                f"/api/v1/documents/{doc_id}",
                headers={"Authorization": f"Bearer {test_user_token}"}
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["message"] == "Document deleted successfully"

    async def test_error_handling_invalid_document_id(self, async_client: AsyncClient, test_user_token):
        """Test error handling for invalid document ID"""
        invalid_id = "00000000-0000-0000-0000-000000000000"
        
        response = await async_client.get(
            f"/api/v1/documents/{invalid_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_error_handling_invalid_chat_id(self, async_client: AsyncClient, test_user_token, test_documents):
        """Test error handling for invalid chat ID"""
        invalid_chat_id = "00000000-0000-0000-0000-000000000000"
        doc_id = str(test_documents[0].uuid)
        
        response = await async_client.post(
            f"/api/v1/chats/{invalid_chat_id}/documents/{doc_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_permission_check_other_user_document(self, async_client: AsyncClient, test_user_token, async_session):
        """Test that users can't access other users' documents"""
        # Create a document for a different user (mock scenario)
        from app.models.user import User
        
        # Create another user
        other_user = User(
            email="other@test.com",
            hashed_password="dummy",
            full_name="Other User",
            is_superuser=False
        )
        async_session.add(other_user)
        await async_session.commit()
        
        # Create document for other user
        other_doc = await document_crud.create(
            async_session,
            obj_in={
                "filename": "other_user_doc.txt",
                "file_size": 1000,
                "content_type": "text/plain",
                "scope": "app_wide",
                "status": "completed"
            },
            user_id=other_user.uuid
        )
        await async_session.commit()
        
        # Try to access with test_user's token
        response = await async_client.get(
            f"/api/v1/documents/{other_doc.uuid}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_complex_workflow(self, async_client: AsyncClient, test_user_token, async_session, test_user):
        """Test a complex workflow combining multiple operations"""
        # 1. Upload multiple documents with different scopes
        docs_created = []
        
        for i, scope in enumerate(["app_wide", "chat_specific"]):
            file_content = f"Complex workflow test content {i}".encode()
            
            with patch('app.services.rag_service.RAGService.process_document') as mock_process:
                mock_process.return_value = {"vector_id": f"complex_vec_{i}", "chunks": 2}
                
                response = await async_client.post(
                    "/api/v1/documents/upload",
                    headers={"Authorization": f"Bearer {test_user_token}"},
                    files={"file": (f"complex_{i}.txt", io.BytesIO(file_content), "text/plain")},
                    data={"scope": scope}
                )
                
                assert response.status_code == status.HTTP_201_CREATED
                docs_created.append(response.json())
        
        # 2. Create a chat session
        chat_response = await async_client.post(
            "/api/v1/chats/",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"title": "Complex Workflow Chat"}
        )
        assert chat_response.status_code == status.HTTP_201_CREATED
        chat_data = chat_response.json()
        
        # 3. Associate documents with the chat
        doc_ids = [doc["uuid"] for doc in docs_created]
        assoc_response = await async_client.post(
            f"/api/v1/chats/{chat_data['uuid']}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"document_ids": doc_ids}
        )
        assert assoc_response.status_code == status.HTTP_200_OK
        
        # 4. Get chat documents and verify
        get_response = await async_client.get(
            f"/api/v1/chats/{chat_data['uuid']}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert get_response.status_code == status.HTTP_200_OK
        chat_docs = get_response.json()
        assert len(chat_docs) == 2
        
        # 5. Remove one document from chat
        remove_response = await async_client.delete(
            f"/api/v1/chats/{chat_data['uuid']}/documents/{doc_ids[0]}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert remove_response.status_code == status.HTTP_200_OK
        
        # 6. Verify only one document remains
        final_get_response = await async_client.get(
            f"/api/v1/chats/{chat_data['uuid']}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert final_get_response.status_code == status.HTTP_200_OK
        final_chat_docs = final_get_response.json()
        assert len(final_chat_docs) == 1
        assert final_chat_docs[0]["uuid"] == doc_ids[1]

    async def test_pagination_and_search(self, async_client: AsyncClient, test_user_token, async_session, test_user):
        """Test pagination and search functionality"""
        # Create many documents for pagination testing
        for i in range(15):
            await document_crud.create(
                async_session,
                obj_in={
                    "filename": f"pagination_test_{i:02d}.txt",
                    "file_size": 1000 + i,
                    "content_type": "text/plain",
                    "scope": "app_wide" if i % 2 == 0 else "chat_specific",
                    "status": "completed"
                },
                user_id=test_user.uuid
            )
        await async_session.commit()
        
        # Test pagination
        response = await async_client.get(
            "/api/v1/documents/?page=1&per_page=5",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["page"] == 1
        assert data["per_page"] == 5
        assert len(data["data"]) == 5
        assert data["has_more"] is True
        assert data["count"] >= 15  # At least the ones we created
        
        # Test second page
        response = await async_client.get(
            "/api/v1/documents/?page=2&per_page=5",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 2
        assert len(data["data"]) == 5

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
