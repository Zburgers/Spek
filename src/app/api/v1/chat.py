import os
import uuid
from datetime import datetime
from typing import Annotated, Optional, List
from uuid import UUID
import json

from google import genai
from google.genai import types

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...core.config import settings
from ...crud.crud_chat import chat_message, chat_session
from ...schemas.chat import (
    ChatHistoryResponse,
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
    TextChatRequest,
    TextChatResponse,
    VoiceChatRequest,
    VoiceChatResponse,
    UpdateTitleRequest,
)
from ...schemas.user import UserRead
from ...models.chat import ChatMessage

# --- Configuration ---
try:
    GOOGLE_API_KEY = settings.API_KEY
    if not GOOGLE_API_KEY:
        raise KeyError
    
    # Initialize the client - this is the correct way for the new SDK
    client = genai.Client(api_key=GOOGLE_API_KEY)
    
except KeyError:
    print("ERROR: GOOGLE_API_KEY environment variable not set.")
    client = None

router = APIRouter(prefix="/chat", tags=["chat"])

def format_history_for_gemini(messages: List[ChatMessage]) -> List[types.Content]:
    """Converts a list of ChatMessage objects to the Gemini API format using the new SDK."""
    history = []
    for msg in messages:
        if msg.message_type == "assistant":
            # Use ModelContent for assistant messages
            content = types.ModelContent(
                parts=[types.Part.from_text(text=msg.content)]
            )
        else:
            # Use UserContent for user messages
            content = types.UserContent(
                parts=[types.Part.from_text(text=msg.content)]
            )
        history.append(content)
    return history

@router.post("/text", response_model=TextChatResponse)
async def text_chat(
    request: TextChatRequest,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TextChatResponse:
    """Send a text message and get a real AI response."""
    
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured. Please check API key configuration."
        )
    
    session_uuid: UUID

    # 1. Create or get chat session
    if request.session_id:
        # If session_id is provided, ensure it exists and belongs to the user
        try:
            session_uuid = UUID(request.session_id)
        except ValueError:
            print(f"ERROR: Invalid session_id format: {request.session_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format"
            )
        
        session = await chat_session.get(db, uuid=session_uuid)
        if not session or session.user_id != current_user['uuid']:
            print(f"ERROR: Chat session not found or unauthorized access. Session ID: {session_uuid}, User ID: {current_user['uuid']}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Chat session not found"
            )
        print(f"DEBUG: Using existing session: {session_uuid}")
    else:
        # Create a new session if no ID is provided
        session_create = ChatSessionCreate(
            user_id=current_user['uuid'],
            title=request.message[:50] if len(request.message) > 3 else "New Chat"  # Simplified title creation
        )
        session = await chat_session.create(db, obj_in=session_create)
        session_uuid = session.uuid
        print(f"DEBUG: Created new session: {session_uuid}")

    # 2. Save the user's new message to the database
    print(f"DEBUG: Saving user message to session: {session_uuid}")
    user_message = ChatMessageCreate(
        session_id=str(session_uuid),
        content=request.message,
        message_type="user",
    )
    await chat_message.create(db, obj_in=user_message)

    # 3. Fetch recent chat history for context (Sliding Window Strategy)
    print(f"DEBUG: Fetching recent messages for session: {session_uuid}")
    recent_messages = await chat_message.get_by_session(db, session_id=session_uuid, limit=20)
    print(f"DEBUG: Found {len(recent_messages)} recent messages")

    # 4. Format the history for the Gemini API using the new SDK
    formatted_history = format_history_for_gemini(recent_messages[:-1])  # Exclude the current message
    print(f"DEBUG: Formatted {len(formatted_history)} messages for Gemini API")

    # 5. Integrate with the Gemini AI model using the new SDK
    ai_response_content = ""
    try:
        print(f"DEBUG: Preparing Gemini API request with {len(formatted_history)} history messages")
        # Prepare the contents - include history and current message
        contents = formatted_history + [types.UserContent(
            parts=[types.Part.from_text(text=request.message)]
        )]
        
        print(f"DEBUG: Sending request to Gemini API")
        # Generate content using the new SDK
        response = client.models.generate_content(
            model='gemini-2.0-flash-001',  # Updated to latest model
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
                thinking_config=types.ThinkingConfig(thinking_budget=0)  # Disable thinking for faster responses
            )
        )
        
        ai_response_content = response.text
        print(f"DEBUG: Received AI response: {len(ai_response_content)} characters")

    except Exception as e:
        # Handle potential API errors gracefully
        print(f"ERROR: An error occurred with the Gemini API: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI service is currently unavailable. Please try again later."
        )

    # 6. Save the AI's response to the database
    print(f"DEBUG: Saving AI response to session: {session_uuid}")
    ai_message = ChatMessageCreate(
        session_id=str(session_uuid),
        content=ai_response_content,
        message_type="assistant",
    )
    await chat_message.create(db, obj_in=ai_message)

    # 7. Return the response to the frontend
    print(f"DEBUG: Returning response for session: {session_uuid}")
    return TextChatResponse(
        message=ai_response_content,
        session_id=str(session_uuid),
        timestamp=datetime.utcnow(),
    )


@router.post("/text/stream")
async def text_chat_stream(
    request: TextChatRequest,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
):
    """Send a text message and get a streaming AI response."""
    
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured. Please check API key configuration."
        )

    async def generate_stream():
        session_uuid: UUID

        # 1. Create or get chat session
        if request.session_id:
            try:
                session_uuid = UUID(request.session_id)
            except ValueError:
                yield f"data: {json.dumps({'error': 'Invalid session ID format'})}\n\n"
                return
            
            session = await chat_session.get(db, uuid=session_uuid)
            if not session or session.user_id != current_user['uuid']:
                yield f"data: {json.dumps({'error': 'Chat session not found'})}\n\n"
                return
        else:
            # Create a new session
            session_create = ChatSessionCreate(
                user_id=current_user['uuid'],
                title=request.message[:50] if len(request.message) > 3 else "New Chat"
            )
            session = await chat_session.create(db, obj_in=session_create)
            session_uuid = session.uuid
            
            # Send session ID to frontend
            yield f"data: {json.dumps({'session_id': str(session_uuid)})}\n\n"

        # 2. Save user message
        user_message = ChatMessageCreate(
            session_id=str(session_uuid),
            content=request.message,
            message_type="user",
        )
        await chat_message.create(db, obj_in=user_message)

        # 3. Get chat history
        recent_messages = await chat_message.get_by_session(db, session_id=session_uuid, limit=20)
        formatted_history = format_history_for_gemini(recent_messages[:-1])

        # 4. Stream AI response
        try:
            contents = formatted_history + [types.UserContent(
                parts=[types.Part.from_text(text=request.message)]
            )]
            
            # Start streaming response
            full_response = ""
            response_stream = client.models.generate_content_stream(
                model='gemini-2.0-flash-001',
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=4096,  # Increased token limit
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                )
            )
            
            for chunk in response_stream:
                if chunk.text:
                    full_response += chunk.text
                    # Send chunk to frontend
                    yield f"data: {json.dumps({'chunk': chunk.text})}\n\n"

            # 5. Save complete AI response to database
            ai_message = ChatMessageCreate(
                session_id=str(session_uuid),
                content=full_response,
                message_type="assistant",
            )
            await chat_message.create(db, obj_in=ai_message)
            
            # Send completion signal
            yield f"data: {json.dumps({'complete': True})}\n\n"

        except Exception as e:
            print(f"ERROR: Streaming error: {e}")
            yield f"data: {json.dumps({'error': 'AI service temporarily unavailable'})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )


@router.post("/voice", response_model=VoiceChatResponse)
async def voice_chat(
    request: VoiceChatRequest,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> VoiceChatResponse:
    """Send voice message and get AI response."""
    
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured. Please check API key configuration."
        )
    
    # TODO: Implement STT to convert audio to text
    # For now, assume we have the text
    text_content = "Voice message received"  # This would come from STT

    # Create or get existing session
    if request.session_id:
        try:
            session_uuid = UUID(request.session_id)
            session = await chat_session.get(db, uuid=session_uuid)
            if not session or session.user_id != current_user['uuid']:
                print(f"ERROR: Voice chat session not found or unauthorized: {session_uuid}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat session not found"
                )
            session_id = str(session_uuid)
            print(f"DEBUG: Using existing voice session: {session_id}")
        except ValueError:
            print(f"ERROR: Invalid voice session_id format: {request.session_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format"
            )
    else:
        session_create = ChatSessionCreate(
            user_id=current_user['uuid'],
            title="Voice Chat",
            is_active=True,
        )
        session = await chat_session.create(db, obj_in=session_create)
        session_id = str(session.uuid)
        print(f"DEBUG: Created new voice session: {session_id}")

    # Save user voice message
    print(f"DEBUG: Saving voice message to session: {session_id}")
    user_message = ChatMessageCreate(
        content=text_content,
        message_type="user",
        session_id=session_id,
    )
    await chat_message.create(db, obj_in=user_message)

    # Generate AI response using new SDK
    try:
        print(f"DEBUG: Generating voice chat response")
        response = client.models.generate_content(
            model='gemini-2.0-flash-001',
            contents=[types.UserContent(parts=[types.Part.from_text(text=text_content)])],
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=1024,
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
        )
        ai_response = response.text
        print(f"DEBUG: Generated voice response: {len(ai_response)} characters")
    except Exception as e:
        print(f"ERROR: Error generating voice chat response: {e}")
        ai_response = "I'm sorry, I couldn't process your voice message right now. Please try again."

    # Save AI response
    print(f"DEBUG: Saving voice AI response to session: {session_id}")
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

@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: UUID,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> ChatHistoryResponse:
    """Get chat history for a specific session."""
    print(f"DEBUG: Getting chat history for session: {session_id}")
    
    # Verify session belongs to current user
    session = await chat_session.get(db, uuid=session_id)
    if not session or session.user_id != current_user['uuid']:
        print(f"ERROR: Chat history session not found or unauthorized: {session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    # Get messages for the session
    messages = await chat_message.get_by_session(db, session_id=session_id)
    total_messages = len(messages)
    print(f"DEBUG: Retrieved {total_messages} messages for session {session_id}")

    # Convert SQLAlchemy models to Pydantic schemas
    message_schemas = [
        ChatMessageRead(
            id=str(msg.id),
            content=msg.content,
            message_type=msg.message_type,
            session_id=str(msg.session_id),
            created_at=msg.created_at,
            updated_at=msg.updated_at,
        )
        for msg in messages
    ]

    return ChatHistoryResponse(
        session_id=str(session_id),
        messages=message_schemas,
        total_messages=total_messages,
    )


@router.get("/sessions", response_model=List[ChatSessionRead])
async def get_user_chat_sessions(
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> List[ChatSessionRead]:
    """Get all chat sessions for the current user."""
    print(f"DEBUG: Getting chat sessions for user: {current_user['uuid']}")
    
    # Get all active sessions for the current user
    sessions = await chat_session.get_by_user(db, user_id=current_user['uuid'])
    print(f"DEBUG: Found {len(sessions)} sessions for user")
    
    return sessions


@router.post("/sessions", response_model=ChatSessionRead)
async def create_new_chat_session(
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    title: Optional[str] = "New Chat",
) -> ChatSessionRead:
    """Create a new chat session for the current user."""
    print(f"DEBUG: Creating new chat session for user: {current_user['uuid']}")
    
    session_create = ChatSessionCreate(
        user_id=current_user['uuid'],
        title=title or "New Chat",
        is_active=True,
    )
    
    session = await chat_session.create(db, obj_in=session_create)
    print(f"DEBUG: Created new session: {session.uuid}")
    
    return session


@router.put("/sessions/{session_id}/title")
async def update_chat_session_title(
    session_id: UUID,
    request: UpdateTitleRequest,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> ChatSessionRead:
    """Update the title of a chat session."""
    print(f"DEBUG: Updating title for session: {session_id}")
    
    # Verify session belongs to current user
    session = await chat_session.get(db, uuid=session_id)
    if not session or session.user_id != current_user['uuid']:
        print(f"ERROR: Chat session not found or unauthorized: {session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Update the title
    updated_session = await chat_session.update_title(db, uuid=session_id, title=request.title)
    if not updated_session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update session title",
        )
    
    print(f"DEBUG: Successfully updated session title: {session_id}")
    return updated_session


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: UUID,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict:
    """Delete (deactivate) a chat session."""
    print(f"DEBUG: Deleting session: {session_id}")
    
    # Verify session belongs to current user
    session = await chat_session.get(db, uuid=session_id)
    if not session or session.user_id != current_user['uuid']:
        print(f"ERROR: Chat session not found or unauthorized: {session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Deactivate the session (soft delete)
    deactivated_session = await chat_session.deactivate(db, uuid=session_id)
    if not deactivated_session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session",
        )
    
    print(f"DEBUG: Successfully deleted session: {session_id}")
    return {"message": "Chat session deleted successfully", "session_id": str(session_id)}