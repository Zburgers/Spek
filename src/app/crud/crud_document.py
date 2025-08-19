from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.document import Document
from ..schemas.chat import DocumentUploadRequest


class CRUDDocument:
    async def create(self, db: AsyncSession, *, obj_in: DocumentUploadRequest, user_id: UUID) -> Document:
        db_obj = Document(
            user_id=user_id,
            file_name=obj_in.file_name,
            file_type=obj_in.file_type,
            file_size=obj_in.file_size,
            content=obj_in.content,
            status="uploaded",
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get(self, db: AsyncSession, uuid: UUID) -> Optional[Document]:
        result = await db.execute(select(Document).where(Document.uuid == uuid))
        return result.scalar_one_or_none()

    async def get_by_user(self, db: AsyncSession, user_id: UUID) -> list[Document]:
        result = await db.execute(select(Document).where(Document.user_id == user_id))
        return list(result.scalars().all())

    async def update_status(self, db: AsyncSession, *, uuid: UUID, status: str) -> Optional[Document]:
        db_obj = await self.get(db, uuid)
        if db_obj:
            db_obj.status = status
            await db.commit()
            await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, uuid: UUID) -> Optional[Document]:
        db_obj = await self.get(db, uuid)
        if db_obj:
            await db.delete(db_obj)
            await db.commit()
        return db_obj


document = CRUDDocument()
