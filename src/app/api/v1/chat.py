import uuid
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...crud.crud_chat import chat_message, chat_session
from ...schemas.chat import (
    ChatHistoryResponse,
    ChatMessageCreate,
    ChatSessionCreate,
    TextChatRequest,
    TextChatResponse,
    VoiceChatRequest,
    VoiceChatResponse,
)
from ...schemas.user import UserRead

router = APIRouter(tags=["chat"])


@router.post("/chat/text", response_model=TextChatResponse)
async def text_chat(
    request: TextChatRequest,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> TextChatResponse:
    """Send a text message and get AI response."""

    # Create or get existing session
    session_id = request.session_id or str(uuid.uuid4())

    if not request.session_id:
        # Create new session
        session_create = ChatSessionCreate(
            user_id=current_user.uuid,
            title=request.message[:50] + "..." if len(request.message) > 50 else request.message,
            is_active=True,
        )
        session = await chat_session.create(db, obj_in=session_create)
        session_id = str(session.uuid)

    # Save user message
    user_message = ChatMessageCreate(
        content=request.message,
        message_type="user",
        session_id=session_id,
    )
    await chat_message.create(db, obj_in=user_message)

    # TODO: Integrate with AI model for response
    # For now, return a mock response
    ai_response = f"I received your message: '{request.message}'. This is a mock response from the AI model."

    # Save AI response
    ai_message = ChatMessageCreate(
        content=ai_response,
        message_type="assistant",
        session_id=session_id,
    )
    await chat_message.create(db, obj_in=ai_message)

    return TextChatResponse(
        message=ai_response,
        session_id=session_id,
        timestamp=datetime.utcnow(),
    )


@router.post("/chat/voice", response_model=VoiceChatResponse)
async def voice_chat(
    request: VoiceChatRequest,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> VoiceChatResponse:
    """Send voice message and get AI response."""

    # TODO: Implement STT to convert audio to text
    # For now, assume we have the text
    text_content = "Voice message received"  # This would come from STT

    # Create or get existing session
    session_id = request.session_id or str(uuid.uuid4())

    if not request.session_id:
        session_create = ChatSessionCreate(
            user_id=current_user.uuid,
            title="Voice Chat",
            is_active=True,
        )
        session = await chat_session.create(db, obj_in=session_create)
        session_id = str(session.uuid)

    # Save user voice message
    user_message = ChatMessageCreate(
        content=text_content,
        message_type="user",
        session_id=session_id,
    )
    await chat_message.create(db, obj_in=user_message)

    # TODO: Integrate with AI model for response
    ai_response = "I received your voice message. This is a mock response from the AI model."

    # Save AI response
    ai_message = ChatMessageCreate(
        content=ai_response,
        message_type="assistant",
        session_id=session_id,
    )
    await chat_message.create(db, obj_in=ai_message)

    # TODO: Implement TTS to convert response to audio
    audio_response = None  # This would be the TTS output

    return VoiceChatResponse(
        text_response=ai_response,
        audio_response=audio_response,
        session_id=session_id,
        timestamp=datetime.utcnow(),
    )


@router.get("/chat/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> ChatHistoryResponse:
    """Get chat history for a specific session."""

    # Verify session belongs to current user
    session = await chat_session.get(db, session_id)
    if not session or session.user_id != current_user.uuid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    # Get messages for the session
    messages = await chat_message.get_by_session(db, session_id)
    total_messages = await chat_message.get_session_message_count(db, session_id)

    return ChatHistoryResponse(
        session_id=str(session_id),
        messages=messages,
        total_messages=total_messages,
    )
