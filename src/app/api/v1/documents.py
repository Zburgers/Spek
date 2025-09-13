from typing import List
from uuid import UUID
import json
import re

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...core.utils import queue
from ...crud.crud_document import document
from ...services.rag import rag_service
from ...schemas.chat import (
    DocumentQueryRequest,
    DocumentQueryResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentStatusUpdate,
    DocumentRead,
)
from ...schemas.user import UserRead

router = APIRouter(tags=["documents"])

def get_user_uuid(user):
    """Helper function to safely extract UUID from user object (Pydantic model or dict)."""
    if isinstance(user, dict):
        return UUID(user["uuid"]) if isinstance(user["uuid"], str) else user["uuid"]
    else:
        return user.uuid
 
@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
):
    """Get document information and content."""
    
    db_document = await document.get(db, doc_id)
    if not db_document or db_document.user_id != get_user_uuid(current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return {
        "document_id": str(db_document.uuid),
        "file_name": db_document.file_name,
        "file_type": db_document.file_type,
        "file_size": db_document.file_size,
        "status": db_document.status,
        "uploaded_at": db_document.created_at,
        "content": db_document.content,  # Base64 encoded content
    }


@router.post("/documents/query", response_model=DocumentQueryResponse)
async def query_document(
    request: DocumentQueryRequest,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> DocumentQueryResponse:
    """Query a document with natural language questions using RAG."""
    
    # Verify document exists and belongs to user
    db_document = await document.get(db, request.document_id)
    if not db_document or db_document.user_id != get_user_uuid(current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    try:
        # **NEW: Use RAG service for document querying**
        rag_result = await rag_service.retrieve_context(
            query=request.query,
            user_id=get_user_uuid(current_user),
            document_filter=UUID(request.document_id)  # Filter to specific document
        )
        
        if rag_result.retrieved_chunks:
            # Found relevant context from the document
            answer = f"Based on the document '{db_document.file_name}':\n\n{rag_result.retrieved_chunks[0].text}"
            confidence = rag_result.retrieved_chunks[0].score if rag_result.retrieved_chunks else 0.5
            
            # Could integrate with LLM here for better answer generation
            # For now, return the most relevant chunk
        else:
            # No relevant context found
            answer = f"I couldn't find relevant information in the document '{db_document.file_name}' to answer your question: '{request.query}'"
            confidence = 0.0
        
        return DocumentQueryResponse(
            answer=answer,
            source_document=db_document.file_name,
            confidence=confidence,
            timestamp=db_document.created_at,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document query failed: {str(e)}",
        )


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
):
    """Delete a document and its associated vectors."""
    
    print(f"DEBUG DELETE: Starting delete for document: {doc_id}")
    print(f"DEBUG DELETE: Current user type: {type(current_user)}")
    print(f"DEBUG DELETE: Current user content: {current_user}")
    
    try:
        user_uuid = get_user_uuid(current_user)
        print(f"DEBUG DELETE: Extracted user UUID: {user_uuid}")
        
        db_document = await document.get(db, doc_id)
        print(f"DEBUG DELETE: Document found: {db_document is not None}")
        
        if not db_document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        print(f"DEBUG DELETE: Delete operation completed successfully")
        return {"message": "Document deleted successfully", "document_id": str(doc_id)}
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"ERROR DELETE: Document deletion failed with exception: {e}")
        print(f"ERROR DELETE: Exception type: {type(e).__name__}")
        print(f"ERROR DELETE: Exception args: {e.args}")
        import traceback
        print(f"ERROR DELETE: Full traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document deletion failed: {str(e)}",
        )


@router.get("/documents")
async def list_user_documents(
    response: Response,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> List[dict]:
    """List all documents for the current user."""
    
    # Disable caching for documents list to ensure fresh data after deletions
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    print(f"DEBUG: current_user type: {type(current_user)}")
    print(f"DEBUG: current_user content: {current_user}")
    user_uuid = get_user_uuid(current_user)
    print(f"DEBUG: extracted user_uuid: {user_uuid}")
    
    documents = await document.get_by_user(db, user_uuid)
    
    return [
        {
            "uuid": str(doc.uuid),  # Frontend expects 'uuid'
            "title": doc.file_name,  # Frontend expects 'title'
            "file_name": doc.file_name,
            "filename": doc.file_name,  # Some parts expect 'filename'
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "processing_status": doc.status,  # Frontend expects 'processing_status'
            "status": doc.status,
            "scope": doc.scope,  # CRITICAL: Frontend filters by scope
            "created_at": doc.created_at,
            "uploaded_at": doc.created_at,
        }
        for doc in documents
    ]


# =============================================================================
# Chat-Document Association Endpoints (RAG Document Control)
# =============================================================================

@router.get("/chats/{chat_id}/documents", response_model=dict)
async def get_chat_documents(
    chat_id: UUID,
    response: Response,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
):
    """Get documents associated with a specific chat session."""
    
    # Disable caching for chat documents to ensure fresh data after deletions
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    try:
        user_uuid = get_user_uuid(current_user)
        
        # Get all app-wide documents for this user
        app_wide_docs = await document.get_multi_by_user_id(db, user_id=user_uuid, scope="app_wide")
        
        # Get chat-specific documents for this chat
        chat_specific_docs = await document.get_multi_by_chat_id(db, chat_id=chat_id, user_id=user_uuid)
        
        # Get selected document IDs for this chat
        selected_doc_ids = await document.get_selected_document_ids_for_chat(db, chat_id=chat_id)
        
        return {
            "app_wide_documents": [
                {
                    "id": str(doc.uuid),
                    "filename": doc.file_name,
                    "file_type": doc.file_type,
                    "status": doc.status,
                    "created_at": doc.created_at,
                    "scope": doc.scope,
                }
                for doc in app_wide_docs
            ],
            "chat_specific_documents": [
                {
                    "id": str(doc.uuid),
                    "filename": doc.file_name,
                    "file_type": doc.file_type,
                    "status": doc.status,
                    "created_at": doc.created_at,
                    "scope": doc.scope,
                }
                for doc in chat_specific_docs
            ],
            "selected_document_ids": [str(doc_id) for doc_id in selected_doc_ids],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat documents: {str(e)}"
        )


@router.post("/chats/{chat_id}/documents")
async def associate_documents_with_chat(
    chat_id: UUID,
    request: dict,  # {"document_ids": [UUID], "selected": bool}
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
):
    """Associate documents with a chat session and set their selection state."""
    try:
        user_uuid = get_user_uuid(current_user)
        document_ids = [UUID(doc_id) for doc_id in request.get("document_ids", [])]
        selected = request.get("selected", True)
        
        # Update or create chat-document associations
        await document.update_chat_document_associations(
            db, 
            chat_id=chat_id, 
            document_ids=document_ids, 
            selected=selected,
            user_id=user_uuid
        )
        
        return {"message": f"Successfully {'selected' if selected else 'deselected'} {len(document_ids)} documents for chat"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to associate documents with chat: {str(e)}"
        )
    
@router.post("/chats/{chat_id}/documents/upload", response_model=DocumentUploadResponse)
async def upload_chat_specific_document(
    chat_id: UUID,
    file: UploadFile = File(...),
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
):
    """Upload a document specific to a chat session."""
    try:
        print(f"DEBUG CHAT UPLOAD: chat_id={chat_id}, user={current_user}")
        print(f"DEBUG CHAT UPLOAD: file parameter: filename={file.filename}, content_type={file.content_type}")
        user_uuid = get_user_uuid(current_user)
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Filename cannot be empty"
            )
        safe_filename = re.sub(r'[^\w\s\-_\.]', '_', file.filename)
        safe_filename = re.sub(r'\s+', '_', safe_filename)
        file_content = await file.read()
        print(f"DEBUG CHAT UPLOAD: file content size={len(file_content)} bytes")
        if len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File cannot be empty"
            )
        content_encoded = file_content.hex()
        doc_data = {
            "file_name": safe_filename,
            "file_type": file.content_type or "application/octet-stream",
            "file_size": len(file_content),
            "content": content_encoded,
            "scope": "chat_specific",
            "chat_id": chat_id,
        }
        new_document = await document.create(db, obj_in=doc_data, user_id=user_uuid)
        try:
            await queue.pool.enqueue_job("process_document_for_rag", str(new_document.uuid))
        except Exception as queue_error:
            print(f"WARNING: Failed to enqueue RAG processing job: {queue_error}")
        return DocumentUploadResponse(
            document_id=str(new_document.uuid),
            filename=new_document.file_name,
            status=new_document.status,
            processing_status=new_document.status,
            scope=new_document.scope,
            message=f"Document '{safe_filename}' uploaded successfully for chat and queued for processing"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error uploading chat document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload chat document: {str(e)}"
        )


@router.post("/chats/{chat_id}/documents/{document_id}")
async def add_single_document_to_chat(
    chat_id: UUID,
    document_id: UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
):
    """Add a single document to a chat session (for backward compatibility)."""
    try:
        user_uuid = get_user_uuid(current_user)
        
        # Update or create chat-document association for single document
        await document.update_chat_document_associations(
            db, 
            chat_id=chat_id, 
            document_ids=[document_id], 
            selected=True,
            user_id=user_uuid
        )
        
        return {"message": "Document added to chat successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add document to chat: {str(e)}"
        )


@router.post("/chats/{chat_id}/documents/upload", response_model=DocumentUploadResponse)
async def upload_chat_specific_document(
    chat_id: UUID,
    file: UploadFile = File(...),
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
):
    """Upload a document specific to a chat session."""
    try:
        # Debug: log incoming request details
        print(f"DEBUG CHAT UPLOAD: chat_id={chat_id}, user={current_user}")
        print(f"DEBUG CHAT UPLOAD: file parameter: filename={file.filename}, content_type={file.content_type}")
        user_uuid = get_user_uuid(current_user)
        
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Filename cannot be empty"
            )
        
        # Sanitize filename: remove/replace potentially problematic characters
        safe_filename = re.sub(r'[^\w\s\-_\.]', '_', file.filename)
        safe_filename = re.sub(r'\s+', '_', safe_filename)  # Replace spaces with underscores
        
        # Read file content and debug size
        file_content = await file.read()
        print(f"DEBUG CHAT UPLOAD: file content size={len(file_content)} bytes")
        if len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File cannot be empty"
            )
        
        # Encode binary content to hex string (same as regular upload)
        content_encoded = file_content.hex()
        
        # Create document with chat-specific scope
        doc_data = {
            "file_name": safe_filename,
            "file_type": file.content_type or "application/octet-stream",
            "file_size": len(file_content),
            "content": content_encoded,
            "scope": "chat_specific",
            "chat_id": chat_id,
        }
        
        # Create document in database
        new_document = await document.create(db, obj_in=doc_data, user_id=user_uuid)
        
        # Queue for RAG processing with properly encoded content
        try:
            await queue.pool.enqueue_job(
                "process_document_for_rag",
                str(new_document.uuid)
            )
        except Exception as queue_error:
            # Log the error but don't fail the upload
            print(f"WARNING: Failed to enqueue RAG processing job: {queue_error}")
        
        return DocumentUploadResponse(
            document_id=str(new_document.uuid),
            filename=new_document.file_name,
            status=new_document.status,
            processing_status=new_document.status,
            scope=new_document.scope,
            message=f"Document '{safe_filename}' uploaded successfully for chat and queued for processing"
        )
    except HTTPException:
        # Re-raise HTTP exceptions as is
        raise
    except Exception as e:
        print(f"Error uploading chat document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload chat document: {str(e)}"
        )


@router.delete("/chats/{chat_id}/documents/{document_id}")
async def remove_document_from_chat(
    chat_id: UUID,
    document_id: UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
):
    """Remove a document association from a chat session."""
    try:
        user_uuid = get_user_uuid(current_user)
        
        # Remove the chat-document association
        await document.remove_chat_document_association(
            db, 
            chat_id=chat_id, 
            document_id=document_id,
            user_id=user_uuid
        )
        
        return {"message": "Document removed from chat successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove document from chat: {str(e)}"
        )


@router.get("/chats/{chat_id}/rag-context")
async def get_rag_context_for_chat(
    chat_id: UUID,
    query: str,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
):
    """Get RAG context filtered by selected documents for a specific chat."""
    try:
        user_uuid = get_user_uuid(current_user)
        
        # Get selected document IDs for this chat
        selected_doc_ids = await document.get_selected_document_ids_for_chat(db, chat_id=chat_id)
        
        if not selected_doc_ids:
            return {"context": "", "sources": []}
        
        # Get RAG context using only selected documents
        context_result = await rag_service.get_context_for_documents(
            query=query, 
            document_ids=selected_doc_ids
        )
        
        return {
            "context": context_result.get("context", ""),
            "sources": context_result.get("sources", []),
            "document_count": len(selected_doc_ids)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get RAG context for chat: {str(e)}"
        )


@router.patch("/documents/{document_id}/status", response_model=DocumentRead)
async def update_document_status(
    document_id: UUID,
    status_update: DocumentStatusUpdate,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> DocumentRead:
    """Update document processing status."""
    try:
        user_uuid = get_user_uuid(current_user)
        
        # Get document and verify ownership
        db_document = await document.get(db, document_id)
        if not db_document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        if db_document.user_id != user_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this document"
            )
        
        # Update status
        updated_document = await document.update_status(
            db, uuid=document_id, status=status_update.status
        )
        
        if not updated_document:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update document status"
            )
        
        return DocumentRead(
            uuid=updated_document.uuid,
            filename=updated_document.file_name,
            file_size=updated_document.file_size,
            content_type=updated_document.file_type,
            status=updated_document.status,
            scope=updated_document.scope,
            created_at=updated_document.created_at,
            updated_at=updated_document.updated_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update document status: {str(e)}"
        )


# WebSocket endpoint for live document status updates
@router.websocket("/documents/status-updates")
async def document_status_websocket(
    websocket: WebSocket,
    db: AsyncSession = Depends(async_get_db),
):
    """WebSocket endpoint for real-time document status updates."""
    await websocket.accept()
    
    try:
        while True:
            # Wait for messages from client (could be ping or document ID to monitor)
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_text("pong")
                continue
            
            # If it's a document ID, start monitoring that document
            try:
                document_id = UUID(data)
                db_document = await document.get(db, document_id)
                
                if db_document:
                    status_data = {
                        "document_id": str(db_document.uuid),
                        "status": db_document.status,
                        "filename": db_document.file_name,
                        "scope": db_document.scope,
                        "updated_at": db_document.updated_at.isoformat() if db_document.updated_at else None
                    }
                    await websocket.send_text(json.dumps(status_data))
                else:
                    await websocket.send_text(json.dumps({"error": "Document not found"}))
                    
            except ValueError:
                await websocket.send_text(json.dumps({"error": "Invalid document ID format"}))
                
    except WebSocketDisconnect:
        print("Client disconnected from document status WebSocket")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()
