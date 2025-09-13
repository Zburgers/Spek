from sqlalchemy.ext.asyncio import AsyncSession

from ..models.message_document import MessageDocument
from ..schemas.chat import MessageDocumentCreate


class CRUDMessageDocument:
    async def create(self, db: AsyncSession, *, obj_in: MessageDocumentCreate) -> MessageDocument:
        # Create the association using keyword arguments with the specific field names
        db_obj = MessageDocument(
            message_id=obj_in.message_id,
            document_id=obj_in.document_id
        )
        
        db.add(db_obj)
        await db.flush()  # Flush to get the object in the database without committing
        return db_obj


crud_message_document = CRUDMessageDocument()
