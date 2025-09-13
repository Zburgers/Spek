import uuid as uuid_pkg
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.database import Base


class Document(Base):
    __tablename__ = "document"

    # Primary keys and required fields (no defaults)
    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)
    user_id: Mapped[uuid_pkg.UUID] = mapped_column(ForeignKey("user.uuid"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Base64 encoded content
    
    # Fields with defaults (must come after non-default fields for dataclass compatibility)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(default_factory=uuid_pkg.uuid4, primary_key=True, unique=True, init=False)
    status: Mapped[str] = mapped_column(String(20), default="uploaded", nullable=False, init=False)  # uploaded, processed, error
    scope: Mapped[str] = mapped_column(String(20), default="app_wide", nullable=False, init=False)  # 'app_wide' | 'chat_specific'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default_factory=lambda: datetime.now(UTC), init=False)
    
    # Optional fields (can have None as default)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, default=None, init=False)
    chat_id: Mapped[Optional[uuid_pkg.UUID]] = mapped_column(ForeignKey("chat_session.uuid"), nullable=True, index=True, init=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="documents", init=False)
    chat_session: Mapped[Optional["ChatSession"]] = relationship("ChatSession", back_populates="documents", init=False)
    chat_associations: Mapped[list["ChatDocument"]] = relationship("ChatDocument", back_populates="document", cascade="all, delete-orphan", init=False)
    message_associations: Mapped[list["MessageDocument"]] = relationship(
        "MessageDocument",
        back_populates="document",
        cascade="all, delete-orphan",
        init=False
    )
