from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chat import ChatMessage, ChatSession
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

    async def get_by_user(self, db: AsyncSession, user_id: UUID) -> list[ChatSession]:
        result = await db.execute(
            select(ChatSession).where(ChatSession.user_id == user_id, ChatSession.is_active)
        )
        return list(result.scalars().all())

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
            session_id=obj_in.session_id,
            content=obj_in.content,
            message_type=obj_in.message_type,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_session(self, db: AsyncSession, session_id: UUID, limit: int = 100) -> list[ChatMessage]:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_session_message_count(self, db: AsyncSession, session_id: UUID) -> int:
        result = await db.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        return len(result.scalars().all())


chat_session = CRUDChatSession()
chat_message = CRUDChatMessage()
