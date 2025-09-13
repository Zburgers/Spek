import uuid as uuid_pkg
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.database import Base


class ChatDocument(Base):
    """Association table for chat sessions and documents with selection state"""
    __tablename__ = "chat_document"

    # Required fields without defaults
    chat_id: Mapped[uuid_pkg.UUID] = mapped_column(ForeignKey("chat_session.uuid"), nullable=False, index=True)
    document_id: Mapped[uuid_pkg.UUID] = mapped_column(ForeignKey("document.uuid"), nullable=False, index=True)
    
    # Fields with defaults (must come after non-default fields)
    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(default_factory=uuid_pkg.uuid4, primary_key=True, unique=True, init=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, init=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default_factory=lambda: datetime.now(UTC), init=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default_factory=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), init=False)
    
    # Relationships
    chat_session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="document_associations", init=False)
    document: Mapped["Document"] = relationship("Document", back_populates="chat_associations", init=False)