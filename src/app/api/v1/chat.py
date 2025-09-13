import os
import uuid
from datetime import datetime
from typing import Annotated, Optional, List
from uuid import UUID
import json
import socket
import dns.resolver

from google import genai
from google.genai import types

from fastapi import APIRouter, Depends, HTTPException, status,Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession


from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...core.config import settings
from ...crud.crud_chat import chat_message, chat_session
from ...crud.crud_message_document import crud_message_document
from ...services.rag import rag_service
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
    MessageDocumentCreate,
    DocumentRead,
)
from ...schemas.user import UserRead
from ...models.chat import ChatMessage

# --- Configuration ---
try:
    GOOGLE_API_KEY = settings.API_KEY
    print(f"DEBUG INIT: API_KEY settings object: {type(settings.API_KEY)}")
    print(f"DEBUG INIT: API_KEY is None: {settings.API_KEY is None}")
    
    if not GOOGLE_API_KEY:
        print(f"DEBUG INIT: API_KEY is falsy")
        raise KeyError("API_KEY is not set or is empty")
    
    # Check the actual secret value
    api_key_value = GOOGLE_API_KEY.get_secret_value()
    print(f"DEBUG INIT: API key length: {len(api_key_value) if api_key_value else 0}")
    print(f"DEBUG INIT: API key preview: {api_key_value[:10] + '...' if api_key_value and len(api_key_value) > 10 else 'SHORT_OR_EMPTY'}")
    print(f"DEBUG INIT: API key has whitespace: {api_key_value != api_key_value.strip() if api_key_value else 'N/A'}")
    
    # Initialize the client - this is the correct way for the new SDK
    client = genai.Client(api_key=api_key_value)
    print("DEBUG INIT: Successfully initialized Gemini client")

except KeyError as ke:
    print(f"ERROR INIT: KeyError during API key setup: {ke}")
    client = None
except Exception as init_error:
    print(f"ERROR INIT: Unexpected error during client initialization: {init_error}")
    print(f"ERROR INIT: Error type: {type(init_error).__name__}")
    client = None

router = APIRouter(prefix="/chat", tags=["chat"])

def get_user_uuid(user):
    """Helper function to safely extract UUID from user object (Pydantic model or dict)."""
    if isinstance(user, dict):
        return UUID(user["uuid"]) if isinstance(user["uuid"], str) else user["uuid"]
    else:
        return user.uuid

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
        if not session or session.user_id != get_user_uuid(current_user):
            print(f"ERROR: Chat session not found or unauthorized access. Session ID: {session_uuid}, User ID: {get_user_uuid(current_user)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Chat session not found"
            )
        print(f"DEBUG: Using existing session: {session_uuid}")
    else:
        # Create a new session if no ID is provided
        session_create = ChatSessionCreate(
            user_id=get_user_uuid(current_user),
            title=request.message[:50] if len(request.message) > 3 else "New Chat"  # Simplified title creation
        )
        session = await chat_session.create(db, obj_in=session_create)
        session_uuid = session.uuid
        print(f"DEBUG: Created new session: {session_uuid}")

    # 2. Save the user's new message to the database
    print(f"DEBUG: Saving user message to session: {session_uuid}")
    user_message_schema = ChatMessageCreate(
        session_id=str(session_uuid),
        content=request.message,
        message_type="user",
    )
    user_message = await chat_message.create(db, obj_in=user_message_schema)

    # Store document associations for the user message
    if request.selected_document_ids:
        for doc_id in request.selected_document_ids:
            message_doc_assoc = MessageDocumentCreate(
                message_id=user_message.id,
                document_id=doc_id
            )
            await crud_message_document.create(db, obj_in=message_doc_assoc)
        await db.commit()

    # 3. Fetch recent chat history for context (Sliding Window Strategy)
    print(f"DEBUG: Fetching recent messages for session: {session_uuid}")
    recent_messages = await chat_message.get_by_session(db, session_id=session_uuid, limit=20)
    print(f"DEBUG: Found {len(recent_messages)} recent messages")

    # 4. Format the history for the Gemini API using the new SDK
    formatted_history = format_history_for_gemini(recent_messages[:-1])  # Exclude the current message
    print(f"DEBUG: Formatted {len(formatted_history)} messages for Gemini API")

    # 5. **NEW: RAG Integration - Retrieve relevant context**
    final_message = request.message
    rag_metadata = {}
    
    try:
        # Use selected documents if provided, otherwise check general availability
        if request.selected_document_ids:
            print(f"DEBUG: RAG context requested for {len(request.selected_document_ids)} documents.")
            rag_result = await rag_service.retrieve_context(
                query=request.message,
                user_id=get_user_uuid(current_user),
                document_ids=request.selected_document_ids  # Pass the list of selected doc IDs
            )
        else:
            # Fallback to general RAG if no specific documents are selected
            rag_availability = await rag_service.check_rag_availability(get_user_uuid(current_user))
            if rag_availability.get("rag_available", False):
                print(f"DEBUG: RAG available, retrieving context for query from all user documents.")
                rag_result = await rag_service.retrieve_context(
                    query=request.message,
                    user_id=get_user_uuid(current_user)
                )
            else:
                rag_result = None

        # Use augmented prompt if context was found
        if rag_result and rag_result.retrieved_chunks:
            final_message = rag_result.augmented_prompt
            rag_metadata = rag_result.metadata
            print(f"DEBUG: Using RAG-augmented prompt with {len(rag_result.retrieved_chunks)} retrieved chunks.")
        else:
            print(f"DEBUG: No relevant RAG context found or used, using original message.")

    except Exception as rag_error:
        # Don't fail the entire request if RAG fails
        print(f"WARNING: RAG retrieval failed, using original message: {rag_error}")

    # 6. Integrate with the Gemini AI model using the new SDK
    ai_response_content = ""
    try:
        print(f"DEBUG: Preparing Gemini API request with {len(formatted_history)} history messages")
        print(f"DEBUG: API key available: {bool(settings.API_KEY)}")
        
        # Test DNS resolution before making API call
        try:
            ip_addresses = socket.gethostbyname_ex('generativelanguage.googleapis.com')
            print(f"DEBUG: DNS resolution successful: {ip_addresses[2]}")
        except socket.gaierror as dns_error:
            print(f"DEBUG: DNS resolution failed: {dns_error}")
            
        # Prepare the contents - include history and current message (potentially RAG-augmented)
        contents = formatted_history + [types.UserContent(
            parts=[types.Part.from_text(text=final_message)]
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
        print(f"DEBUG: Exception type: {type(e).__name__}")
        if hasattr(e, 'errno'):
            print(f"DEBUG: Error errno: {e.errno}")
        if "name resolution" in str(e).lower():
            print(f"DEBUG: This appears to be a DNS/name resolution issue in regular chat")
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI service is currently unavailable. Please try again later."
        )

    # 7. Save the AI's response to the database
    print(f"DEBUG: Saving AI response to session: {session_uuid}")
    ai_message = ChatMessageCreate(
        session_id=str(session_uuid),
        content=ai_response_content,
        message_type="assistant",
    )
    await chat_message.create(db, obj_in=ai_message)

    # 8. Return the response to the frontend
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
            if not session or session.user_id != get_user_uuid(current_user):
                yield f"data: {json.dumps({'error': 'Chat session not found'})}\n\n"
                return
        else:
            # Create a new session
            session_create = ChatSessionCreate(
                user_id=get_user_uuid(current_user),
                title=request.message[:50] if len(request.message) > 3 else "New Chat"
            )
            session = await chat_session.create(db, obj_in=session_create)
            session_uuid = session.uuid
            
            # Send session ID to frontend
            yield f"data: {json.dumps({'session_id': str(session_uuid)})}\n\n"

        # 2. Save user message
        user_message_schema = ChatMessageCreate(
            session_id=str(session_uuid),
            content=request.message,
            message_type="user",
        )
        user_message = await chat_message.create(db, obj_in=user_message_schema)

        # Store document associations for the user message
        print(f"[MESSAGE DOC ASSOC] Request has selected_document_ids: {request.selected_document_ids}")
        print(f"[MESSAGE DOC ASSOC] User message ID: {user_message.id}")
        if request.selected_document_ids:
            print(f"[MESSAGE DOC ASSOC] Creating {len(request.selected_document_ids)} document associations")
            for doc_id in request.selected_document_ids:
                print(f"[MESSAGE DOC ASSOC] Creating association: message_id={user_message.id}, document_id={doc_id}")
                try:
                    message_doc_assoc = MessageDocumentCreate(
                        message_id=user_message.id,
                        document_id=doc_id
                    )
                    created_assoc = await crud_message_document.create(db, obj_in=message_doc_assoc)
                    print(f"[MESSAGE DOC ASSOC] Successfully created association: {created_assoc}")
                except Exception as e:
                    print(f"[MESSAGE DOC ASSOC] Error creating association: {e}")
                    print(f"[MESSAGE DOC ASSOC] Error type: {type(e).__name__}")
            await db.commit()
            print(f"[MESSAGE DOC ASSOC] Committed all document associations")
        else:
            print(f"[MESSAGE DOC ASSOC] No selected documents to associate")

        # 3. Get chat history
        recent_messages = await chat_message.get_by_session(db, session_id=session_uuid, limit=20)
        formatted_history = format_history_for_gemini(recent_messages[:-1])

        # 4. Stream AI response
        try:
            # Debug API key and network connectivity
            print(f"DEBUG STREAM: Starting streaming request")
            print(f"DEBUG STREAM: API key available: {bool(settings.API_KEY)}")
            if settings.API_KEY:
                api_key_preview = settings.API_KEY.get_secret_value()[:10] + "..." if len(settings.API_KEY.get_secret_value()) > 10 else "SHORT_KEY"
                print(f"DEBUG STREAM: API key preview: {api_key_preview}")
            
            # Test DNS resolution for Google AI API
            try:
                print(f"DEBUG STREAM: Testing DNS resolution for generativelanguage.googleapis.com")
                ip_addresses = socket.gethostbyname_ex('generativelanguage.googleapis.com')
                print(f"DEBUG STREAM: DNS resolution successful: {ip_addresses[2]}")
            except socket.gaierror as dns_error:
                print(f"DEBUG STREAM: DNS resolution failed: {dns_error}")
                print(f"DEBUG STREAM: DNS error code: {dns_error.errno}")
            
            # Test basic connectivity
            try:
                print(f"DEBUG STREAM: Testing socket connectivity to generativelanguage.googleapis.com:443")
                sock = socket.create_connection(('generativelanguage.googleapis.com', 443), timeout=10)
                sock.close()
                print(f"DEBUG STREAM: Socket connectivity successful")
            except Exception as conn_error:
                print(f"DEBUG STREAM: Socket connectivity failed: {conn_error}")
            
            contents = formatted_history + [types.UserContent(
                parts=[types.Part.from_text(text=request.message)]
            )]
            
            print(f"DEBUG STREAM: Prepared {len(contents)} content items for streaming")
            print(f"DEBUG STREAM: Starting generate_content_stream call")
            
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
            
            print(f"DEBUG STREAM: Successfully created response stream")
            
            for chunk in response_stream:
                if chunk.text:
                    full_response += chunk.text
                    # Send chunk to frontend
                    yield f"data: {json.dumps({'chunk': chunk.text})}\n\n"

            print(f"DEBUG STREAM: Completed streaming, total response length: {len(full_response)}")

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
            print(f"DEBUG STREAM: Exception type: {type(e).__name__}")
            print(f"DEBUG STREAM: Exception args: {e.args}")
            
            # Additional network-specific debugging
            if hasattr(e, 'errno'):
                print(f"DEBUG STREAM: Error errno: {e.errno}")
            if hasattr(e, 'strerror'):
                print(f"DEBUG STREAM: Error strerror: {e.strerror}")
                
            # Check if it's a name resolution error specifically
            if "name resolution" in str(e).lower() or "temporary failure" in str(e).lower():
                print(f"DEBUG STREAM: This appears to be a DNS/name resolution issue")
                print(f"DEBUG STREAM: Checking system DNS configuration...")
                try:
                    with open('/etc/resolv.conf', 'r') as f:
                        resolv_content = f.read()
                        print(f"DEBUG STREAM: /etc/resolv.conf content: {resolv_content}")
                except Exception as dns_check_error:
                    print(f"DEBUG STREAM: Could not read DNS config: {dns_check_error}")
            
            yield f"data: {json.dumps({'error': 'AI service temporarily unavailable'})}\n\n"
            
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
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
            if not session or session.user_id != get_user_uuid(current_user):
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
            user_id=get_user_uuid(current_user),
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
    if not session or session.user_id != get_user_uuid(current_user):
        print(f"ERROR: Chat history session not found or unauthorized: {session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    # Get messages for the session
    messages = await chat_message.get_by_session_with_documents(db, session_id=session_id)
    print(f"""[LOAD HISTORY] Fetched {len(messages)} messages with associations.""")
    total_messages = len(messages)

    # Convert SQLAlchemy models to Pydantic schemas
    message_schemas = []
    for msg in messages:
        print(f"""[LOAD HISTORY] Processing message ID {msg.id}, content: '{msg.content[:30]}...'""")
        print(f"""[LOAD HISTORY] Found {len(msg.document_associations)} document associations for message {msg.id}""")
        documents = []
        if msg.document_associations:
            for assoc in msg.document_associations:
                if assoc.document:
                    documents.append(DocumentRead.from_orm(assoc.document))
                else:
                    print(f"[LOAD HISTORY] Warning: Association found for message {msg.id} but document is None.")

        message_schemas.append(
            ChatMessageRead(
                id=str(msg.id),
                content=msg.content,
                message_type=msg.message_type,
                session_id=str(msg.session_id),
                created_at=msg.created_at,
                updated_at=msg.updated_at,
                documents=documents,
                uuid=msg.uuid
            )
        )
    print(f"[LOAD HISTORY] Final message schemas: {message_schemas}")

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
    print(f"DEBUG: Getting chat sessions for user: {get_user_uuid(current_user)}")
    
    # Get all active sessions for the current user
    sessions = await chat_session.get_by_user(db, user_id=get_user_uuid(current_user))
    print(f"DEBUG: Found {len(sessions)} sessions for user")
    
    return sessions


@router.post("/sessions", response_model=ChatSessionRead)
async def create_new_chat_session(
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    title: Optional[str] = "New Chat",
) -> ChatSessionRead:
    """Create a new chat session for the current user."""
    print(f"DEBUG: Creating new chat session for user: {get_user_uuid(current_user)}")
    
    session_create = ChatSessionCreate(
        user_id=get_user_uuid(current_user),
        title=title or "New Chat",
        is_active=True,
    )
    
    session = await chat_session.create(db, obj_in=session_create)
    print(f"DEBUG: Created new session: {session.uuid}")
    
    return session


@router.put("/sessions/{session_id}/title")
@router.patch("/sessions/{session_id}/title")
async def update_chat_session_title(
    session_id: UUID,
    request: UpdateTitleRequest,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> ChatSessionRead:
    """Update the title of a chat session (PUT or PATCH)."""
    print(f"DEBUG: Updating title for session: {session_id}")
    # Verify session belongs to current user
    session = await chat_session.get(db, uuid=session_id)
    if not session or session.user_id != get_user_uuid(current_user):
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
    if not session or session.user_id != get_user_uuid(current_user):
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