from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
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
from ...services.rag_service import RAGService, RAGError
from ...services.document_processor import DocumentProcessor

router = APIRouter(tags=["documents"])


async def process_document_background(document_id: str):
    """Background task to process uploaded documents."""
    from ...core.db.database import async_get_db
    
    try:
        rag_service = RAGService()
        
        # Create a new database session for the background task
        async for db in async_get_db():
            # Get document from database
            db_document = await document.get(db, UUID(document_id))
            if not db_document:
                return
            
            # Update status to processing
            await document.update_status(db, uuid=db_document.uuid, status="processing")
            
            # Process the document
            processed_text, status = rag_service.process_uploaded_document(
                db_document.content,
                db_document.file_type,
                db_document.file_name
            )
            
            # Update with processed results
            await document.update_processed_text(
                db,
                uuid=db_document.uuid,
                processed_text=processed_text,
                status=status
            )
            break  # Exit the async generator
        
    except Exception as e:
        # Mark as error if processing fails
        try:
            async for db in async_get_db():
                await document.update_status(db, uuid=UUID(document_id), status="error")
                break
        except:
            pass


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> DocumentUploadResponse:
    """Upload a document for processing and querying."""
    
    try:
        # Read file content
        content = await file.read()
        content_hex = content.hex()  # Store as hex-encoded
        
        # Check if file type is supported for processing
        content_type = file.content_type or "application/octet-stream"
        is_processable = DocumentProcessor.is_supported_type(content_type)
        
        # Create upload request
        upload_request = DocumentUploadRequest(
            file_name=file.filename,
            file_type=content_type,
            file_size=len(content),
            content=content_hex,
        )
        
        # Save document to database
        db_document = await document.create(db, obj_in=upload_request, user_id=current_user.uuid)
        
        # If the document type is supported, queue it for processing
        if is_processable:
            background_tasks.add_task(process_document_background, str(db_document.uuid))
        else:
            # Mark as unsupported type
            await document.update_status(db, uuid=db_document.uuid, status="unsupported_type")
        
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
        "content": db_document.content,  # Hex encoded content
        "has_processed_text": bool(db_document.processed_text),
        "is_queryable": db_document.status == "processed" and bool(db_document.processed_text),
    }


@router.post("/documents/query", response_model=DocumentQueryResponse)
async def query_document(
    request: DocumentQueryRequest,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> DocumentQueryResponse:
    """Query a document with natural language questions using RAG."""
    
    # Verify document exists and belongs to user
    db_document = await document.get(db, UUID(request.document_id))
    if not db_document or db_document.user_id != current_user.uuid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Check if document is processed and ready for querying
    if db_document.status not in ["processed"]:
        if db_document.status == "processing":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document is still being processed. Please try again later.",
            )
        elif db_document.status == "unsupported_type":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document type is not supported for querying.",
            )
        elif db_document.status == "error":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document processing failed. Please try re-uploading the document.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document is not ready for querying.",
            )
    
    try:
        # Initialize RAG service
        rag_service = RAGService()
        
        # Use processed text if available, otherwise fall back to original content
        content_to_query = db_document.processed_text or db_document.content
        
        # Perform RAG query
        answer, relevant_chunks, confidence = await rag_service.query_document(
            request.query,
            content_to_query,
            db_document.file_name
        )
        
        # Extract relevant excerpts for response
        relevant_excerpts = [chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text 
                           for chunk in relevant_chunks[:3]]
        
        return DocumentQueryResponse(
            answer=answer,
            source_document=db_document.file_name,
            confidence=confidence,
            timestamp=db_document.created_at,
            relevant_excerpts=relevant_excerpts if relevant_excerpts else None,
        )
        
    except RAGError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document query failed: {str(e)}",
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
            "is_queryable": doc.status == "processed" and bool(doc.processed_text),
        }
        for doc in documents
    ]
