"""
End-to-end workflow tests for the centralized document management system.
Tests complete user workflows and edge cases.
"""

import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status
import json
import io
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import os

from app.models.document import Document
from app.models.chat import Chat
from app.models.chat_document import ChatDocument
from app.crud.crud_document import document_crud
from app.crud.crud_chat import chat_crud


class TestCompleteWorkflows:
    """Test complete user workflows for document management"""

    async def test_new_user_complete_workflow(self, async_client: AsyncClient, test_user_token, async_session: AsyncSession, test_user):
        """Test complete workflow for a new user"""
        print("\n=== Testing Complete New User Workflow ===")
        
        # Step 1: User starts with no documents
        response = await async_client.get(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        initial_data = response.json()
        print(f"Initial documents: {initial_data['count']}")
        
        # Step 2: User uploads their first app-wide document
        app_content = b"This is my first app-wide document with important information"
        
        with patch('app.services.rag_service.RAGService.process_document') as mock_process:
            mock_process.return_value = {"vector_id": "app_vec_123", "chunks": 5}
            
            upload_response = await async_client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {test_user_token}"},
                files={"file": ("my_notes.txt", io.BytesIO(app_content), "text/plain")},
                data={"scope": "app_wide"}
            )
        
        assert upload_response.status_code == status.HTTP_201_CREATED
        app_doc = upload_response.json()
        print(f"Uploaded app-wide document: {app_doc['filename']}")
        
        # Step 3: User uploads a chat-specific document
        chat_content = b"This is specific to my research project chat"
        
        with patch('app.services.rag_service.RAGService.process_document') as mock_process:
            mock_process.return_value = {"vector_id": "chat_vec_456", "chunks": 3}
            
            upload_response = await async_client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {test_user_token}"},
                files={"file": ("research_notes.txt", io.BytesIO(chat_content), "text/plain")},
                data={"scope": "chat_specific"}
            )
        
        assert upload_response.status_code == status.HTTP_201_CREATED
        chat_doc = upload_response.json()
        print(f"Uploaded chat-specific document: {chat_doc['filename']}")
        
        # Step 4: User creates a new chat session
        chat_response = await async_client.post(
            "/api/v1/chats/",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"title": "My Research Project Chat"}
        )
        assert chat_response.status_code == status.HTTP_201_CREATED
        chat_data = chat_response.json()
        print(f"Created chat session: {chat_data['title']}")
        
        # Step 5: User associates both documents with the chat
        assoc_response = await async_client.post(
            f"/api/v1/chats/{chat_data['uuid']}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"document_ids": [app_doc["uuid"], chat_doc["uuid"]]}
        )
        assert assoc_response.status_code == status.HTTP_200_OK
        print(f"Associated {assoc_response.json()['associations_created']} documents with chat")
        
        # Step 6: User views documents in the chat
        chat_docs_response = await async_client.get(
            f"/api/v1/chats/{chat_data['uuid']}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert chat_docs_response.status_code == status.HTTP_200_OK
        chat_docs = chat_docs_response.json()
        assert len(chat_docs) == 2
        print(f"Chat has {len(chat_docs)} associated documents")
        
        # Step 7: User decides to remove the app-wide document from this specific chat
        remove_response = await async_client.delete(
            f"/api/v1/chats/{chat_data['uuid']}/documents/{app_doc['uuid']}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert remove_response.status_code == status.HTTP_200_OK
        print("Removed app-wide document from chat")
        
        # Step 8: User verifies only chat-specific document remains
        final_chat_docs_response = await async_client.get(
            f"/api/v1/chats/{chat_data['uuid']}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert final_chat_docs_response.status_code == status.HTTP_200_OK
        final_chat_docs = final_chat_docs_response.json()
        assert len(final_chat_docs) == 1
        assert final_chat_docs[0]["uuid"] == chat_doc["uuid"]
        print("Verified only chat-specific document remains in chat")
        
        # Step 9: User still sees both documents in global list
        all_docs_response = await async_client.get(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert all_docs_response.status_code == status.HTTP_200_OK
        all_docs = all_docs_response.json()
        assert all_docs["count"] >= 2  # Should still have both documents
        print(f"Global document list still shows {all_docs['count']} documents")

    async def test_document_scope_isolation(self, async_client: AsyncClient, test_user_token, async_session: AsyncSession, test_user):
        """Test that document scopes work correctly in different contexts"""
        print("\n=== Testing Document Scope Isolation ===")
        
        # Create documents with different scopes
        docs = []
        for i, scope in enumerate(["app_wide", "chat_specific"]):
            content = f"Content for {scope} document {i}".encode()
            
            with patch('app.services.rag_service.RAGService.process_document') as mock_process:
                mock_process.return_value = {"vector_id": f"scope_vec_{i}", "chunks": 2}
                
                response = await async_client.post(
                    "/api/v1/documents/upload",
                    headers={"Authorization": f"Bearer {test_user_token}"},
                    files={"file": (f"{scope}_doc_{i}.txt", io.BytesIO(content), "text/plain")},
                    data={"scope": scope}
                )
                
                assert response.status_code == status.HTTP_201_CREATED
                docs.append(response.json())
                print(f"Created {scope} document: {response.json()['filename']}")
        
        # Test filtering by scope
        app_wide_response = await async_client.get(
            "/api/v1/documents/?scope=app_wide",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert app_wide_response.status_code == status.HTTP_200_OK
        app_wide_docs = app_wide_response.json()["data"]
        print(f"App-wide filter returned {len(app_wide_docs)} documents")
        
        chat_specific_response = await async_client.get(
            "/api/v1/documents/?scope=chat_specific",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert chat_specific_response.status_code == status.HTTP_200_OK
        chat_specific_docs = chat_specific_response.json()["data"]
        print(f"Chat-specific filter returned {len(chat_specific_docs)} documents")
        
        # Verify scope isolation
        for doc in app_wide_docs:
            assert doc["scope"] == "app_wide"
        
        for doc in chat_specific_docs:
            assert doc["scope"] == "chat_specific"

    async def test_concurrent_operations(self, async_client: AsyncClient, test_user_token, async_session: AsyncSession, test_user):
        """Test concurrent document operations"""
        print("\n=== Testing Concurrent Operations ===")
        
        # Create a chat first
        chat_response = await async_client.post(
            "/api/v1/chats/",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"title": "Concurrent Test Chat"}
        )
        chat_id = chat_response.json()["uuid"]
        
        # Upload multiple documents concurrently
        upload_tasks = []
        for i in range(5):
            content = f"Concurrent upload test document {i}".encode()
            
            async def upload_doc(index, content):
                with patch('app.services.rag_service.RAGService.process_document') as mock_process:
                    mock_process.return_value = {"vector_id": f"concurrent_vec_{index}", "chunks": 1}
                    
                    response = await async_client.post(
                        "/api/v1/documents/upload",
                        headers={"Authorization": f"Bearer {test_user_token}"},
                        files={"file": (f"concurrent_{index}.txt", io.BytesIO(content), "text/plain")},
                        data={"scope": "app_wide"}
                    )
                    return response
            
            upload_tasks.append(upload_doc(i, content))
        
        # Execute concurrent uploads
        upload_results = await asyncio.gather(*upload_tasks)
        
        # Verify all uploads succeeded
        doc_ids = []
        for result in upload_results:
            assert result.status_code == status.HTTP_201_CREATED
            doc_ids.append(result.json()["uuid"])
        
        print(f"Successfully uploaded {len(doc_ids)} documents concurrently")
        
        # Associate all documents with chat concurrently
        assoc_response = await async_client.post(
            f"/api/v1/chats/{chat_id}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"document_ids": doc_ids}
        )
        assert assoc_response.status_code == status.HTTP_200_OK
        assert assoc_response.json()["associations_created"] == 5
        print("Successfully associated all documents with chat")

    async def test_large_document_handling(self, async_client: AsyncClient, test_user_token):
        """Test handling of larger documents"""
        print("\n=== Testing Large Document Handling ===")
        
        # Create a larger document (1MB)
        large_content = b"A" * (1024 * 1024)  # 1MB of 'A's
        
        with patch('app.services.rag_service.RAGService.process_document') as mock_process:
            mock_process.return_value = {"vector_id": "large_vec_123", "chunks": 100}
            
            response = await async_client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {test_user_token}"},
                files={"file": ("large_document.txt", io.BytesIO(large_content), "text/plain")},
                data={"scope": "app_wide"}
            )
        
        assert response.status_code == status.HTTP_201_CREATED
        doc_data = response.json()
        assert doc_data["file_size"] == 1024 * 1024
        print(f"Successfully uploaded large document: {doc_data['file_size']} bytes")

    async def test_error_recovery_scenarios(self, async_client: AsyncClient, test_user_token, async_session: AsyncSession, test_user):
        """Test error recovery scenarios"""
        print("\n=== Testing Error Recovery Scenarios ===")
        
        # Test 1: Upload with RAG service failure
        content = b"Test document for RAG failure"
        
        with patch('app.services.rag_service.RAGService.process_document') as mock_process:
            mock_process.side_effect = Exception("RAG service unavailable")
            
            response = await async_client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {test_user_token}"},
                files={"file": ("rag_fail_test.txt", io.BytesIO(content), "text/plain")},
                data={"scope": "app_wide"}
            )
            
            # Should still create document but with failed status
            assert response.status_code == status.HTTP_201_CREATED
            doc_data = response.json()
            assert doc_data["status"] in ["failed", "error"]
            print(f"Handled RAG failure gracefully: {doc_data['status']}")
        
        # Test 2: Associate with non-existent chat
        fake_chat_id = "00000000-0000-0000-0000-000000000000"
        
        response = await async_client.post(
            f"/api/v1/chats/{fake_chat_id}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"document_ids": [doc_data["uuid"]]}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        print("Correctly rejected association with non-existent chat")
        
        # Test 3: Associate non-existent document
        real_chat = await chat_crud.create(
            async_session,
            obj_in={"title": "Error Test Chat"},
            user_id=test_user.uuid
        )
        await async_session.commit()
        
        fake_doc_id = "00000000-0000-0000-0000-000000000000"
        
        response = await async_client.post(
            f"/api/v1/chats/{real_chat.uuid}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"document_ids": [fake_doc_id]}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        print("Correctly rejected association with non-existent document")

    async def test_performance_edge_cases(self, async_client: AsyncClient, test_user_token, async_session: AsyncSession, test_user):
        """Test performance with edge cases"""
        print("\n=== Testing Performance Edge Cases ===")
        
        # Create many documents to test pagination
        doc_ids = []
        for i in range(25):  # Create 25 documents
            doc = await document_crud.create(
                async_session,
                obj_in={
                    "filename": f"perf_test_{i:03d}.txt",
                    "file_size": 1000 + i,
                    "content_type": "text/plain",
                    "scope": "app_wide" if i % 2 == 0 else "chat_specific",
                    "status": "completed"
                },
                user_id=test_user.uuid
            )
            doc_ids.append(str(doc.uuid))
        
        await async_session.commit()
        print(f"Created {len(doc_ids)} documents for performance testing")
        
        # Test pagination performance
        page_1_response = await async_client.get(
            "/api/v1/documents/?page=1&per_page=10",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert page_1_response.status_code == status.HTTP_200_OK
        page_1_data = page_1_response.json()
        assert len(page_1_data["data"]) == 10
        assert page_1_data["has_more"] is True
        print("Page 1: Retrieved 10 documents successfully")
        
        # Test large association operation
        chat = await chat_crud.create(
            async_session,
            obj_in={"title": "Performance Test Chat"},
            user_id=test_user.uuid
        )
        await async_session.commit()
        
        # Associate all documents at once
        assoc_response = await async_client.post(
            f"/api/v1/chats/{chat.uuid}/documents",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={"document_ids": doc_ids}
        )
        assert assoc_response.status_code == status.HTTP_200_OK
        assert assoc_response.json()["associations_created"] == 25
        print("Successfully associated 25 documents in bulk operation")

    async def test_data_consistency(self, async_client: AsyncClient, test_user_token, async_session: AsyncSession, test_user):
        """Test data consistency across operations"""
        print("\n=== Testing Data Consistency ===")
        
        # Create initial state
        doc_content = b"Consistency test document"
        
        with patch('app.services.rag_service.RAGService.process_document') as mock_process:
            mock_process.return_value = {"vector_id": "consistency_vec", "chunks": 2}
            
            upload_response = await async_client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {test_user_token}"},
                files={"file": ("consistency_test.txt", io.BytesIO(doc_content), "text/plain")},
                data={"scope": "app_wide"}
            )
        
        doc_id = upload_response.json()["uuid"]
        
        # Create multiple chats
        chat_ids = []
        for i in range(3):
            chat_response = await async_client.post(
                "/api/v1/chats/",
                headers={"Authorization": f"Bearer {test_user_token}"},
                json={"title": f"Consistency Chat {i+1}"}
            )
            chat_ids.append(chat_response.json()["uuid"])
        
        print(f"Created 3 chats for consistency testing")
        
        # Associate document with all chats
        for chat_id in chat_ids:
            assoc_response = await async_client.post(
                f"/api/v1/chats/{chat_id}/documents/{doc_id}",
                headers={"Authorization": f"Bearer {test_user_token}"}
            )
            assert assoc_response.status_code == status.HTTP_200_OK
        
        print("Associated document with all 3 chats")
        
        # Verify document appears in all chats
        for i, chat_id in enumerate(chat_ids):
            chat_docs_response = await async_client.get(
                f"/api/v1/chats/{chat_id}/documents",
                headers={"Authorization": f"Bearer {test_user_token}"}
            )
            assert chat_docs_response.status_code == status.HTTP_200_OK
            chat_docs = chat_docs_response.json()
            assert len(chat_docs) == 1
            assert chat_docs[0]["uuid"] == doc_id
            print(f"Chat {i+1}: Document correctly associated")
        
        # Remove document from one chat
        remove_response = await async_client.delete(
            f"/api/v1/chats/{chat_ids[0]}/documents/{doc_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert remove_response.status_code == status.HTTP_200_OK
        print("Removed document from Chat 1")
        
        # Verify document still exists in other chats
        for i, chat_id in enumerate(chat_ids):
            chat_docs_response = await async_client.get(
                f"/api/v1/chats/{chat_id}/documents",
                headers={"Authorization": f"Bearer {test_user_token}"}
            )
            chat_docs = chat_docs_response.json()
            
            if i == 0:  # First chat should have no documents
                assert len(chat_docs) == 0
                print("Chat 1: Document correctly removed")
            else:  # Other chats should still have the document
                assert len(chat_docs) == 1
                assert chat_docs[0]["uuid"] == doc_id
                print(f"Chat {i+1}: Document still present")
        
        # Verify document still exists globally
        all_docs_response = await async_client.get(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        all_docs = all_docs_response.json()["data"]
        doc_exists = any(doc["uuid"] == doc_id for doc in all_docs)
        assert doc_exists, "Document should still exist globally"
        print("Document still exists in global list")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
