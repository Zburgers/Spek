from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..models.chat import ChatMessage, ChatSession
from ..models.message_document import MessageDocument
from ..schemas.chat import ChatMessageCreate, ChatSessionCreate


class CRUDChatSession:
    async def create(self, db: AsyncSession, *, obj_in: ChatSessionCreate) -> ChatSession:
        db_obj = ChatSession(
            user_id=obj_in.user_id,
            title=obj_in.title,
            is_active=obj_in.is_active,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get(self, db: AsyncSession, uuid: UUID) -> Optional[ChatSession]:
        result = await db.execute(select(ChatSession).where(ChatSession.uuid == uuid))
        return result.scalar_one_or_none()

    async def get_by_user(self, db: AsyncSession, user_id: UUID) -> List[ChatSession]:
        """
        Retrieve all active chat sessions for a specific user, ordered by creation date (newest first).
        
        Args:
            db (AsyncSession): Database session for executing queries
            user_id (UUID): The UUID of the user whose chat sessions to retrieve
            
        Returns:
            List[ChatSession]: List of chat sessions ordered by created_at descending (newest first)
            
        Example:
            >>> sessions = await chat_session.get_by_user(db, user_id=user.uuid)
            >>> print(f"Found {len(sessions)} sessions for user")
            >>> # sessions[0] will be the most recently created session
        """
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.is_active == True)
            .order_by(ChatSession.created_at.desc())
        )
        return result.scalars().all()

    async def update_title(self, db: AsyncSession, *, uuid: UUID, title: str) -> Optional[ChatSession]:
        db_obj = await self.get(db, uuid)
        if db_obj:
            db_obj.title = title
            await db.commit()
            await db.refresh(db_obj)
        return db_obj

    async def deactivate(self, db: AsyncSession, *, uuid: UUID) -> Optional[ChatSession]:
        db_obj = await self.get(db, uuid)
        if db_obj:
            db_obj.is_active = False
            await db.commit()
            await db.refresh(db_obj)
        return db_obj


class CRUDChatMessage:
    async def create(self, db: AsyncSession, *, obj_in: ChatMessageCreate) -> ChatMessage:
        db_obj = ChatMessage(
            session_id=UUID(obj_in.session_id),  # Convert string to UUID
            content=obj_in.content,
            message_type=obj_in.message_type,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_session(self, db: AsyncSession, session_id: UUID, limit: int = 100) -> List[ChatMessage]:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_session_message_count(self, db: AsyncSession, session_id: UUID) -> int:
        result = await db.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        return len(result.scalars().all())

    async def get_by_session_with_documents(
        self, db: AsyncSession, *, session_id: UUID, limit: int = 100
    ) -> List[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .options(
                joinedload(ChatMessage.document_associations).joinedload(
                    MessageDocument.document
                )
            )
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.unique().scalars().all()

chat_session = CRUDChatSession()
chat_message = CRUDChatMessage()
