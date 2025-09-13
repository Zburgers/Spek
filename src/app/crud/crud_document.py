from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.document import Document
from ..models.chat_document import ChatDocument
from ..schemas.chat import DocumentUploadRequest


class CRUDDocument:
    async def create(self, db: AsyncSession, *, obj_in: DocumentUploadRequest | dict, user_id: UUID) -> Document:
        if isinstance(obj_in, dict):
            db_obj = Document(
                user_id=user_id,
                file_name=obj_in["file_name"],
                file_type=obj_in["file_type"],
                file_size=obj_in["file_size"],
                content=obj_in["content"] if isinstance(obj_in["content"], str) else obj_in["content"].decode("utf-8", errors="ignore"),
            )
            # Set the init=False fields after creation
            db_obj.status = "uploaded"
            db_obj.scope = obj_in.get("scope", "app_wide")
            if obj_in.get("chat_id"):
                db_obj.chat_id = obj_in["chat_id"]
        else:
            db_obj = Document(
                user_id=user_id,
                file_name=obj_in.file_name,
                file_type=obj_in.file_type,
                file_size=obj_in.file_size,
                content=obj_in.content,
            )
            # Set the init=False fields after creation
            db_obj.status = "uploaded"
            db_obj.scope = getattr(obj_in, "scope", "app_wide")
            if hasattr(obj_in, "chat_id") and obj_in.chat_id:
                db_obj.chat_id = obj_in.chat_id
                
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get(self, db: AsyncSession, uuid: UUID) -> Optional[Document]:
        result = await db.execute(select(Document).where(Document.uuid == uuid))
        return result.scalar_one_or_none()

    async def get_by_user(self, db: AsyncSession, user_id: UUID) -> List[Document]:
        result = await db.execute(select(Document).where(Document.user_id == user_id))
        return result.scalars().all()

    async def update_status(self, db: AsyncSession, *, uuid: UUID, status: str) -> Optional[Document]:
        db_obj = await self.get(db, uuid)
        if db_obj:
            db_obj.status = status
            await db.commit()
            await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, uuid: UUID) -> Optional[Document]:
        print(f"DEBUG CRUD DELETE: Starting delete for UUID: {uuid}")
        db_obj = await self.get(db, uuid)
        print(f"DEBUG CRUD DELETE: Found document: {db_obj is not None}")
        
        if db_obj:
            print(f"DEBUG CRUD DELETE: Deleting document from database session")
            await db.delete(db_obj)
            print(f"DEBUG CRUD DELETE: Committing transaction")
            await db.commit()
            print(f"DEBUG CRUD DELETE: Delete operation completed")
        else:
            print(f"DEBUG CRUD DELETE: No document found with UUID {uuid}")
            
        return db_obj

    # =============================================================================
    # RAG Document Control Methods
    # =============================================================================

    async def get_multi_by_user_id(self, db: AsyncSession, *, user_id: UUID, scope: str = None) -> List[Document]:
        """Get documents by user ID, optionally filtered by scope."""
        query = select(Document).where(Document.user_id == user_id)
        if scope:
            query = query.where(Document.scope == scope)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_multi_by_chat_id(self, db: AsyncSession, *, chat_id: UUID, user_id: UUID) -> List[Document]:
        """Get chat-specific documents for a chat session."""
        query = select(Document).where(
            and_(
                Document.chat_id == chat_id,
                Document.user_id == user_id,
                Document.scope == "chat_specific"
            )
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def get_selected_document_ids_for_chat(self, db: AsyncSession, *, chat_id: UUID) -> List[UUID]:
        """Get selected document IDs for a specific chat session."""
        query = select(ChatDocument.document_id).where(
            and_(
                ChatDocument.chat_id == chat_id,
                ChatDocument.selected == True
            )
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def update_chat_document_associations(
        self, 
        db: AsyncSession, 
        *, 
        chat_id: UUID, 
        document_ids: List[UUID], 
        selected: bool,
        user_id: UUID
    ) -> None:
        """Update or create chat-document associations."""
        for doc_id in document_ids:
            # Check if association already exists
            existing_query = select(ChatDocument).where(
                and_(
                    ChatDocument.chat_id == chat_id,
                    ChatDocument.document_id == doc_id
                )
            )
            result = await db.execute(existing_query)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing association
                existing.selected = selected
            else:
                # Create new association
                new_association = ChatDocument(
                    chat_id=chat_id,
                    document_id=doc_id,
                    selected=selected
                )
                db.add(new_association)

        await db.commit()

    async def remove_chat_document_association(
        self, 
        db: AsyncSession, 
        *, 
        chat_id: UUID, 
        document_id: UUID,
        user_id: UUID
    ) -> None:
        """Remove a chat-document association."""
        query = select(ChatDocument).where(
            and_(
                ChatDocument.chat_id == chat_id,
                ChatDocument.document_id == document_id
            )
        )
        result = await db.execute(query)
        association = result.scalar_one_or_none()

        if association:
            await db.delete(association)
            await db.commit()


document = CRUDDocument()
