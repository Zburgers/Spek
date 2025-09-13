import uuid as uuid_pkg
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.database import Base

if TYPE_CHECKING:
    from .chat import ChatMessage
    from .document import Document


class MessageDocument(Base):
    """Association table for messages and documents"""
    __tablename__ = "message_document"

    message_id: Mapped[int] = mapped_column(ForeignKey("chat_message.id"), primary_key=True)
    document_id: Mapped[uuid_pkg.UUID] = mapped_column(ForeignKey("document.uuid"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default_factory=lambda: datetime.now(UTC), init=False)

    # Relationships
    message: Mapped["ChatMessage"] = relationship("ChatMessage", back_populates="document_associations", init=False)
    document: Mapped["Document"] = relationship("Document", back_populates="message_associations", init=False)

    __table_args__ = (PrimaryKeyConstraint('message_id', 'document_id'),)
