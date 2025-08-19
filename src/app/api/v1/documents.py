from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...crud.crud_document import document
from ...schemas.chat import (
    DocumentQueryRequest,
    DocumentQueryResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
)
from ...schemas.user import UserRead

router = APIRouter(tags=["documents"])


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> DocumentUploadResponse:
    """Upload a document for processing and querying."""

    try:
        # Read file content
        content = await file.read()
        content_base64 = content.hex()  # Simple encoding for demo

        # Create upload request
        upload_request = DocumentUploadRequest(
            file_name=file.filename,
            file_type=file.content_type or "application/octet-stream",
            file_size=len(content),
            content=content_base64,
        )

        # Save document to database
        db_document = await document.create(db, obj_in=upload_request, user_id=current_user.uuid)

        return DocumentUploadResponse(
            document_id=str(db_document.uuid),
            file_name=db_document.file_name,
            file_type=db_document.file_type,
            status=db_document.status,
            uploaded_at=db_document.created_at,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document upload failed: {str(e)}",
        )


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
):
    """Get document information and content."""

    db_document = await document.get(db, doc_id)
    if not db_document or db_document.user_id != current_user.uuid:
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
    """Query a document with natural language questions."""

    # Verify document exists and belongs to user
    db_document = await document.get(db, request.document_id)
    if not db_document or db_document.user_id != current_user.uuid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        # TODO: Implement actual document querying with AI
        # This would use RAG (Retrieval-Augmented Generation) or similar
        # For now, return mock response

        answer = f"This is a mock answer to your query: '{request.query}' about the document '{db_document.file_name}'."
        source_document = db_document.file_name
        confidence = 0.85

        return DocumentQueryResponse(
            answer=answer,
            source_document=source_document,
            confidence=confidence,
            timestamp=db_document.created_at,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document query failed: {str(e)}",
        )


@router.get("/documents")
async def list_user_documents(
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> List[dict]:
    """List all documents for the current user."""

    documents = await document.get_by_user(db, current_user.uuid)

    return [
        {
            "document_id": str(doc.uuid),
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "status": doc.status,
            "uploaded_at": doc.created_at,
        }
        for doc in documents
    ]
