from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from ..core.schemas import TimestampSchema, UUIDSchema

class DocumentRead(BaseModel):
    uuid: UUID
    filename: str = Field(alias="file_name")
    file_size: int
    content_type: str = Field(alias="file_type") 
    status: str
    scope: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True

class ChatMessageBase(BaseModel):
    content: str
    message_type: str = Field(description="Type of message: 'user', 'assistant', 'system'")
    session_id: str = Field(description="Chat session identifier")


class ChatMessageCreate(ChatMessageBase):
    pass


class ChatMessageRead(ChatMessageBase, TimestampSchema, UUIDSchema):
    documents: Optional[List[DocumentRead]] = None
    pass


class ChatSessionBase(BaseModel):
    user_id: UUID
    title: Optional[str] = None
    is_active: bool = True


class ChatSessionCreate(ChatSessionBase):
    pass


class ChatSessionRead(ChatSessionBase, TimestampSchema, UUIDSchema):
    pass


class UpdateTitleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100, description="New title for the chat session")


class TextChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    model: Optional[str] = "gpt-4"
    selected_document_ids: Optional[List[UUID]] = Field(
        None, description="List of document UUIDs to use for RAG context"
    )


class TextChatResponse(BaseModel):
    message: str
    session_id: str
    timestamp: datetime


class VoiceChatRequest(BaseModel):
    audio_data: str = Field(description="Base64 encoded audio data")
    session_id: Optional[str] = None
    model: Optional[str] = "gpt-4"


class VoiceChatResponse(BaseModel):
    text_response: str
    audio_response: Optional[str] = Field(description="Base64 encoded audio response")
    session_id: str
    timestamp: datetime


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessageRead]
    total_messages: int


class STTRequest(BaseModel):
    audio_data: str = Field(description="Base64 encoded audio data")
    language: Optional[str] = "en-US"


class STTResponse(BaseModel):
    text: str
    confidence: float
    language: str


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "alloy"
    language: Optional[str] = "en-US"


class TTSResponse(BaseModel):
    audio_data: str = Field(description="Base64 encoded audio data")
    duration: float


class DocumentUploadRequest(BaseModel):
    file_name: str
    file_type: str
    file_size: int
    content: str = Field(description="Base64 encoded file content")


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    processing_status: Optional[str] = None
    scope: str
    message: str


class DocumentStatusUpdate(BaseModel):
    status: str = Field(description="New status: uploaded, processing, completed, failed")
    message: Optional[str] = Field(None, description="Optional status message")

class DocumentQueryRequest(BaseModel):
    document_id: str
    query: str
    session_id: Optional[str] = None


class DocumentQueryResponse(BaseModel):
    answer: str
    source_document: str
    confidence: float
    timestamp: datetime


class ModelInfo(BaseModel):
    id: str
    name: str
    type: str
    capabilities: List[str]
    is_available: bool


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    services: dict[str, str]

class MessageDocumentCreate(BaseModel):
    message_id: int
    document_id: UUID
