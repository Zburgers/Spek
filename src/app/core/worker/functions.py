import asyncio
import logging
import time
from uuid import UUID

import uvloop
try:
    from arq.worker import Worker
    ARQ_AVAILABLE = True
except ImportError:
    Worker = None
    ARQ_AVAILABLE = False
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db.database import async_get_db
from ...crud.crud_document import document
from ...services.document_processing import document_processing_service
from ...services.embedding import embedding_service
from ...services.vector_store import vector_store_service

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


# -------- background tasks --------
async def sample_background_task(ctx: Worker, name: str) -> str:
    await asyncio.sleep(5)
    return f"Task {name} is complete!"


async def process_document_for_rag(ctx: Worker, document_id: str) -> str:
    """
    Process a document for RAG: extract text, chunk it, generate embeddings, and store vectors.
    
    Args:
        ctx: ARQ worker context
        document_id: UUID string of the document to process
        
    Returns:
        Processing result message
    """
    document_uuid = UUID(document_id)
    logger = logging.getLogger(__name__)
    logger.info(f"Starting RAG processing for document: {document_uuid}")
    t0 = time.perf_counter()
    
    try:
        # Get database session (following existing patterns)
        async for db in async_get_db():
            logger.info(f"DEBUG: Got database session for document {document_uuid}")
            
            # Step 1: Retrieve document from database
            db_document = await document.get(db, document_uuid)
            if not db_document:
                raise ValueError(f"Document {document_uuid} not found")
            
            logger.info(f"DEBUG: Found document {document_uuid}, current status: {db_document.status}")
            logger.info(
                "DEBUG: Document meta file_name=%s file_type=%s size=%s scope=%s",
                db_document.file_name,
                db_document.file_type,
                db_document.file_size,
                getattr(db_document, "scope", None),
            )
            
            # Update status to processing - Fixed method call with keyword arguments
            logger.info(f"DEBUG: About to call document.update_status with args: db={type(db)}, uuid={document_uuid}, status='processing'")
            try:
                await document.update_status(db, uuid=document_uuid, status="processing")
                logger.info(f"DEBUG: Successfully updated document {document_uuid} status to processing")
            except Exception as update_error:
                logger.error(f"DEBUG: Failed to update status to processing: {update_error}")
                logger.error(f"DEBUG: Update error type: {type(update_error).__name__}")
                raise update_error
            
            try:
                # Step 2: Process document (extract text and chunk)
                logger.info(f"DEBUG: Starting document processing for {document_uuid}")
                chunks = await document_processing_service.process_document(
                    document_id=document_uuid,
                    content=db_document.content,
                    file_type=db_document.file_type,
                    file_name=db_document.file_name,
                )
                
                if not chunks:
                    logger.warning(f"DEBUG: No chunks extracted from document {document_uuid}")
                    await document.update_status(db, uuid=document_uuid, status="error")
                    return f"No content could be extracted from document {document_uuid}"
                
                logger.info(
                    f"DEBUG: Extracted {len(chunks)} chunks from document {document_uuid}; lengths={[len(c.text) for c in chunks[:3]]}"
                )
                
                # Step 3: Prepare vectors for upload (using Pinecone integrated embeddings)
                # With integrated embedding models, we only need to provide the text
                logger.info(f"DEBUG: Preparing vectors for Pinecone integrated embeddings")
                vectors_data = []
                for i, chunk in enumerate(chunks):
                    vector_data = {
                        "id": f"{document_uuid}_chunk_{chunk.chunk_index}",
                        "metadata": {
                            "text": chunk.text,  # This matches your Pinecone field mapping
                            "document_id": str(document_uuid),
                            "user_id": str(db_document.user_id),
                            "file_name": db_document.file_name,
                            "file_type": db_document.file_type,
                            "chunk_index": chunk.chunk_index,
                            **chunk.metadata
                        }
                    }
                    vectors_data.append(vector_data)
                
                # Step 4: Upload vectors to vector database
                logger.info(f"DEBUG: Uploading {len(vectors_data)} vectors to vector store")
                logger.info(
                    f"DEBUG: Vector store client initialized: {vector_store_service.client is not None}; index initialized: {vector_store_service.index is not None}"
                )
                try:
                    await vector_store_service.ensure_ready()
                except Exception as ensure_err:
                    logger.error(f"DEBUG: ensure_ready failed: {ensure_err}")
                    await document.update_status(db, uuid=document_uuid, status="error")
                    return f"Vector store not ready: {ensure_err}"

                await vector_store_service.upsert_vectors(vectors_data)
                logger.info(f"DEBUG: Successfully uploaded vectors to vector store")
                
                # Step 5: Update document status to processed - Fixed method call
                await document.update_status(db, uuid=document_uuid, status="processed")
                t1 = time.perf_counter()
                logger.info(f"DEBUG: Updated document {document_uuid} status to processed in {t1 - t0:.2f}s")
                
                result_msg = f"Successfully processed document {document_uuid}: {len(chunks)} chunks with integrated embeddings"
                logger.info(result_msg)
                return result_msg
                
            except Exception as processing_error:
                # Update status to error if processing fails - Fixed method call
                logger.error(f"DEBUG: Processing error for document {document_uuid}: {processing_error}")
                await document.update_status(db, uuid=document_uuid, status="error")
                error_msg = f"Error processing document {document_uuid}: {str(processing_error)}"
                logger.error(error_msg)
                return error_msg
            
            break  # Exit the async generator loop
            
    except Exception as e:
        error_msg = f"Failed to process document {document_uuid}: {str(e)}"
        logger.error(error_msg)
        return error_msg

    # Fallback return in case no path above returned (shouldn't normally happen)
    return f"Processing completed for document {document_uuid}"


# -------- base functions --------
async def startup(ctx: Worker) -> None:
    logging.info("Worker Started")


async def shutdown(ctx: Worker) -> None:
    logging.info("Worker end")
