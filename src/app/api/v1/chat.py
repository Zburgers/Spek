import os
import uuid
from datetime import datetime
from typing import Annotated, Optional, List, Any, TYPE_CHECKING, cast
from uuid import UUID
import json
import socket
import dns.resolver

# Google Generative AI SDK (guarded import for Pylance and optional envs)
try:  # type: ignore[reportMissingImports]
    from google import genai  # type: ignore[reportMissingImports]
    from google.genai import types as _genai_types  # type: ignore[reportMissingImports]
except Exception:  # pragma: no cover - safe guard when SDK missing at dev time
    genai = None  # type: ignore[assignment]
    _genai_types = None  # type: ignore[assignment]
    pass

# Alias for type usage; Pylance will treat as Any even if SDK isn't present at runtime
GT = cast(Any, _genai_types)

from fastapi import APIRouter, Depends, HTTPException, status,Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.logger import logging
logger = logging.getLogger(__name__)


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
    DocumentStatus,
)
from ...schemas.user import UserRead
from ...models.chat import ChatMessage

# --- Configuration ---
try:
    GOOGLE_API_KEY = settings.API_KEY
    logger.info(f"DEBUG INIT: API_KEY settings object: {type(settings.API_KEY)}")
    logger.info(f"DEBUG INIT: API_KEY is None: {settings.API_KEY is None}")
    
    if not GOOGLE_API_KEY:
        logger.warning(f"DEBUG INIT: API_KEY is falsy")
        raise KeyError("API_KEY is not set or is empty")
    
    # Check the actual secret value
    api_key_value = GOOGLE_API_KEY.get_secret_value()
    #print(f"DEBUG INIT: API key length: {len(api_key_value) if api_key_value else 0}")
    #print(f"DEBUG INIT: API key preview: {api_key_value[:10] + '...' if api_key_value and len(api_key_value) > 10 else 'SHORT_OR_EMPTY'}")
    #print(f"DEBUG INIT: API key has whitespace: {api_key_value != api_key_value.strip() if api_key_value else 'N/A'}")
    
    # Initialize the client - this is the correct way for the new SDK
    if genai is None:
        raise ImportError("google-genai SDK not available")
    G = cast(Any, genai)
    client = G.Client(api_key=api_key_value)
    logger.info("DEBUG INIT: Successfully initialized Gemini client")

except KeyError as ke:
    logger.error(f"ERROR INIT: KeyError during API key setup: {ke}")
    client = None
except Exception as init_error:
    logger.error(f"ERROR INIT: Unexpected error during client initialization: {init_error}")
    logger.error(f"ERROR INIT: Error type: {type(init_error).__name__}")
    client = None

router = APIRouter(prefix="/chat", tags=["chat"])

# --- Status Normalization Utilities ---
_LEGACY_STATUS_MAP = {"processed": "completed", "error": "failed"}
_LEGACY_STATUS_SEEN = set()

def normalize_document_status(raw: str) -> DocumentStatus:
    """Normalize legacy document statuses to canonical ones.

    Keeps a small in-memory record of legacy values encountered so we log each
    legacy status per distinct raw value only once (avoids log spam).
    """
    if raw in _LEGACY_STATUS_MAP:
        if raw not in _LEGACY_STATUS_SEEN:
            logger.warning(
                f"Encountered legacy document status '{raw}', normalizing to '{_LEGACY_STATUS_MAP[raw]}'"
            )
            _LEGACY_STATUS_SEEN.add(raw)
        raw = _LEGACY_STATUS_MAP[raw]
    try:
        return DocumentStatus(raw)  # type: ignore[arg-type]
    except ValueError:
        logger.warning(f"Unknown document status '{raw}', defaulting to 'failed'")
        return DocumentStatus.failed

def get_user_uuid(user):
    """Helper function to safely extract UUID from user object (Pydantic model or dict)."""
    if isinstance(user, dict):
        return UUID(user["uuid"]) if isinstance(user["uuid"], str) else user["uuid"]
    else:
        return user.uuid

def format_history_for_gemini(messages: List[ChatMessage]) -> List[Any]:
    """Converts a list of ChatMessage objects to the Gemini API format using the new SDK."""
    history = []
    for msg in messages:
        if msg.message_type == "assistant":
            # Use ModelContent for assistant messages
            content = GT.ModelContent(
                parts=[GT.Part.from_text(text=msg.content)]
            )
        else:
            # Use UserContent for user messages
            content = GT.UserContent(
                parts=[GT.Part.from_text(text=msg.content)]
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

    # 1) Create or get session
    if request.session_id:
        try:
            session_uuid = UUID(request.session_id)
        except ValueError:
            logger.error(f"Invalid session_id format: {request.session_id}")
            raise HTTPException(status_code=400, detail="Invalid session ID format")
        session = await chat_session.get(db, uuid=session_uuid)
        if not session or session.user_id != get_user_uuid(current_user):
            logger.error(f"Chat session not found/unauthorized: {session_uuid}")
            raise HTTPException(status_code=404, detail="Chat session not found")
        logger.info(f"Using existing session: {session_uuid}")
    else:
        session_create = ChatSessionCreate(
            user_id=get_user_uuid(current_user),
            title=request.message[:50] if len(request.message) > 3 else "New Chat",
        )
        session = await chat_session.create(db, obj_in=session_create)
        session_uuid = session.uuid
        logger.info(f"Created new session: {session_uuid}")

    # 2) Save user message
    user_message = await chat_message.create(
        db,
        obj_in=ChatMessageCreate(
            session_id=str(session_uuid), content=request.message, message_type="user"
        ),
    )

    # 3) Document associations (optional)
    if request.selected_document_ids:
        try:
            for doc_id in request.selected_document_ids:
                await crud_message_document.create(
                    db,
                    obj_in=MessageDocumentCreate(
                        message_id=user_message.id, document_id=doc_id
                    ),
                )
            await db.commit()
        except Exception as assoc_err:
            logger.error(f"Failed to create document associations: {assoc_err}")
            await db.rollback()
            raise HTTPException(500, detail="Failed to associate documents with the message")

    # 4) History for context
    recent_messages = await chat_message.get_by_session(db, session_id=session_uuid, limit=20)
    formatted_history = format_history_for_gemini(recent_messages[:-1])

    # 5) RAG context
    final_message = request.message
    try:
        rag_result = None
        if request.selected_document_ids:
            rag_result = await rag_service.retrieve_context(
                query=request.message,
                user_id=get_user_uuid(current_user),
                document_ids=request.selected_document_ids,
            )
        else:
            rag_availability = await rag_service.check_rag_availability(
                get_user_uuid(current_user)
            )
            if rag_availability.get("rag_available"):
                rag_result = await rag_service.retrieve_context(
                    query=request.message, user_id=get_user_uuid(current_user)
                )

        if rag_result and rag_result.retrieved_chunks:
            final_message = rag_result.augmented_prompt
            # Pretty chunk log
            lines = [
                "RAG in Chat: Using augmented prompt",
                f"- Retrieved chunks: {len(rag_result.retrieved_chunks)}",
            ]
            for i, c in enumerate(rag_result.retrieved_chunks[:10]):
                doc_id = c.metadata.get("document_id")
                file_name = c.metadata.get("file_name")
                preview = (c.text or "").replace("\n", " ")[:180]
                lines.append(
                    f"  {i+1}. score={c.score:.4f} doc={doc_id} file={file_name} text='{preview}...'"
                )
            if len(rag_result.retrieved_chunks) > 10:
                lines.append(f"  ... (+{len(rag_result.retrieved_chunks)-10} more)")
            logger.info("\n".join(lines))
            logger.info(
                "\n".join(
                    [
                        "RAG in Chat: Context preview",
                        rag_result.context[:2000]
                        + ("..." if len(rag_result.context) > 2000 else ""),
                    ]
                )
            )
        else:
            logger.info("RAG: No relevant context; using original message")
    except Exception as rag_error:
        logger.warning(f"RAG retrieval failed, using original message: {rag_error}")

    # 6) Call Gemini
    try:
        # DNS check (best-effort)
        try:
            socket.gethostbyname_ex("generativelanguage.googleapis.com")
        except Exception as dns_err:
            logger.warning(f"DNS check failed: {dns_err}")

        contents = formatted_history + [
            GT.UserContent(parts=[GT.Part.from_text(text=final_message)])
        ]

        cli = cast(Any, client)
        response = cli.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=contents,
            config=GT.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
                thinking_config=GT.ThinkingConfig(thinking_budget=0),
            ),
        )
        ai_response_content = response.text
        logger.info(f"Gemini response length: {len(ai_response_content)}")
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        errno_val = getattr(e, "errno", None)
        if errno_val is not None:
            logger.error(f"Gemini error errno: {errno_val}")
        if "name resolution" in str(e).lower():
            logger.error("DNS/name resolution issue detected during chat")
        raise HTTPException(503, detail="AI service currently unavailable. Try again later.")

    # 7) Persist AI response
    await chat_message.create(
        db,
        obj_in=ChatMessageCreate(
            session_id=str(session_uuid), content=ai_response_content, message_type="assistant"
        ),
    )

    # 8) Return
    return TextChatResponse(
        message=ai_response_content, session_id=str(session_uuid), timestamp=datetime.utcnow()
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
        try:
            session_uuid: UUID

            # 1) Create or get session
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
                session_create = ChatSessionCreate(
                    user_id=get_user_uuid(current_user),
                    title=request.message[:50] if len(request.message) > 3 else "New Chat",
                )
                session = await chat_session.create(db, obj_in=session_create)
                session_uuid = session.uuid
                # Send session ID to frontend immediately
                yield f"data: {json.dumps({'session_id': str(session_uuid)})}\n\n"

            # 2) Save user message
            user_message = await chat_message.create(
                db,
                obj_in=ChatMessageCreate(
                    session_id=str(session_uuid),
                    content=request.message,
                    message_type="user",
                ),
            )

            # 3) Document associations (optional)
            logger.info(
                f"[STREAM DOC ASSOC] selected_document_ids: {request.selected_document_ids} for message {user_message.id}"
            )
            if request.selected_document_ids:
                for doc_id in request.selected_document_ids:
                    try:
                        await crud_message_document.create(
                            db,
                            obj_in=MessageDocumentCreate(
                                message_id=user_message.id, document_id=doc_id
                            ),
                        )
                    except Exception as assoc_err:
                        logger.error(f"[STREAM DOC ASSOC] Error creating association: {assoc_err}")
                await db.commit()
            else:
                logger.info("[STREAM DOC ASSOC] No selected documents to associate")

            # 4) History and optional RAG context
            recent_messages = await chat_message.get_by_session(
                db, session_id=session_uuid, limit=20
            )
            formatted_history = format_history_for_gemini(recent_messages[:-1])

            final_message = request.message
            try:
                rag_result = None
                if request.selected_document_ids:
                    rag_result = await rag_service.retrieve_context(
                        query=request.message,
                        user_id=get_user_uuid(current_user),
                        document_ids=request.selected_document_ids,
                    )
                else:
                    rag_availability = await rag_service.check_rag_availability(
                        get_user_uuid(current_user)
                    )
                    if rag_availability.get("rag_available"):
                        rag_result = await rag_service.retrieve_context(
                            query=request.message,
                            user_id=get_user_uuid(current_user),
                        )

                if rag_result and rag_result.retrieved_chunks:
                    final_message = rag_result.augmented_prompt
                    # Pretty chunk log
                    lines = [
                        "RAG in Stream: Using augmented prompt",
                        f"- Retrieved chunks: {len(rag_result.retrieved_chunks)}",
                    ]
                    for i, c in enumerate(rag_result.retrieved_chunks[:10]):
                        doc_id = c.metadata.get("document_id")
                        file_name = c.metadata.get("file_name")
                        preview = (c.text or "").replace("\n", " ")[:180]
                        lines.append(
                            f"  {i+1}. score={c.score:.4f} doc={doc_id} file={file_name} text='{preview}...'"
                        )
                    if len(rag_result.retrieved_chunks) > 10:
                        lines.append(
                            f"  ... (+{len(rag_result.retrieved_chunks)-10} more)"
                        )
                    logger.info("\n".join(lines))
                    logger.info(
                        "\n".join(
                            [
                                "RAG in Stream: Context preview",
                                rag_result.context[:2000]
                                + ("..." if len(rag_result.context) > 2000 else ""),
                            ]
                        )
                    )
                else:
                    logger.info("RAG (stream): No relevant context; using original message")
            except Exception as rag_error:
                logger.warning(
                    f"RAG retrieval (stream) failed, using original message: {rag_error}"
                )

            # 5) DNS checks (best-effort)
            try:
                socket.gethostbyname_ex("generativelanguage.googleapis.com")
            except Exception as dns_err:
                logger.warning(f"DEBUG STREAM: DNS resolution failed: {dns_err}")

            # 6) Stream from Gemini
            contents: List[Any] = formatted_history + [
                GT.UserContent(parts=[GT.Part.from_text(text=final_message)])
            ]
            logger.info(
                f"DEBUG STREAM: Prepared {len(contents)} content items; starting streaming call"
            )

            client_nonnull = cast(Any, client)
            response_stream = client_nonnull.models.generate_content_stream(
                model="gemini-2.0-flash-001",
                contents=contents,
                config=GT.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=4096,
                    thinking_config=GT.ThinkingConfig(thinking_budget=0),
                ),
            )

            full_response = ""
            for chunk in response_stream:
                if getattr(chunk, "text", None):
                    full_response += chunk.text
                    yield f"data: {json.dumps({'chunk': chunk.text})}\n\n"

            # Save assistant message
            await chat_message.create(
                db,
                obj_in=ChatMessageCreate(
                    session_id=str(session_uuid),
                    content=full_response,
                    message_type="assistant",
                ),
            )
            yield f"data: {json.dumps({'complete': True})}\n\n"

        except Exception as e:
            logger.error(f"ERROR: Streaming error: {e}")
            errno_val = getattr(e, "errno", None)
            if errno_val is not None:
                logger.error(f"DEBUG STREAM: Error errno: {errno_val}")
            strerror_val = getattr(e, "strerror", None)
            if strerror_val is not None:
                logger.error(f"DEBUG STREAM: Error strerror: {strerror_val}")
            if "name resolution" in str(e).lower() or "temporary failure" in str(e).lower():
                logger.error(
                    "DEBUG STREAM: DNS/name resolution error detected, please check system DNS settings"
                )
            yield f"data: {json.dumps({'error': 'AI service temporarily unavailable'})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
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
                logger.error(f"Voice chat session not found or unauthorized: {session_uuid}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat session not found"
                )
            session_id = str(session_uuid)
            logger.info(f"Using existing voice session: {session_id}")
        except ValueError:
            logger.error(f"Invalid voice session_id format: {request.session_id}")
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
    logger.info(f"Created new voice session: {session_id}")

    # Save user voice message
    logger.info(f"Saving voice message to session: {session_id}")
    user_message = ChatMessageCreate(
        content=text_content,
        message_type="user",
        session_id=session_id,
    )
    await chat_message.create(db, obj_in=user_message)

    # Generate AI response using new SDK
    try:
        logger.info(f"Generating voice chat response")
        client_nonnull = cast(Any, client)
        response = client_nonnull.models.generate_content(
            model='gemini-2.0-flash-001',
            contents=[GT.UserContent(parts=[GT.Part.from_text(text=text_content)])],
            config=GT.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=1024,
                thinking_config=GT.ThinkingConfig(thinking_budget=0)
            )
        )
        ai_response = response.text
        logger.info(f"Generated voice response: {len(ai_response)} characters")
    except Exception as e:
        logger.error(f"Error generating voice chat response: {e}")
        ai_response = "I'm sorry, I couldn't process your voice message right now. Please try again."

    # Save AI response
    logger.info(f"Saving voice AI response to session: {session_id}")
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
    logger.info(f"DEBUG: Getting chat history for session: {session_id}")
    
    # Verify session belongs to current user
    session = await chat_session.get(db, uuid=session_id)
    if not session or session.user_id != get_user_uuid(current_user):
        logger.error(f"ERROR: Chat history session not found or unauthorized: {session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    # Get messages for the session
    messages = await chat_message.get_by_session_with_documents(db, session_id=session_id)
    logger.info(f"""[LOAD HISTORY] Fetched {len(messages)} messages with associations.""")
    total_messages = len(messages)

    # Convert SQLAlchemy models to Pydantic schemas
    message_schemas = []
    for msg in messages:
        logger.info(
            f"""[LOAD HISTORY] Processing message ID {msg.id}, content: '{msg.content[:30]}...'"""
        )
        logger.info(
            f"""[LOAD HISTORY] Found {len(msg.document_associations)} document associations for message {msg.id}"""
        )
        documents = []
        if msg.document_associations:
            for assoc in msg.document_associations:
                if assoc.document:
                    doc = assoc.document
                    documents.append(
                        DocumentRead(
                            uuid=doc.uuid,
                            file_name=doc.file_name,
                            file_size=doc.file_size,
                            file_type=doc.file_type,
                            status=normalize_document_status(doc.status),
                            scope=doc.scope,
                            created_at=doc.created_at,
                            updated_at=doc.updated_at,
                        )
                    )
                else:
                    logger.warning(f"[LOAD HISTORY] Warning: Association found for message {msg.id} but document is None.")

        message_schemas.append(
            ChatMessageRead(
                content=msg.content,
                message_type=msg.message_type,
                session_id=str(msg.session_id),
                created_at=msg.created_at,
                updated_at=msg.updated_at,
                documents=documents,
                uuid=msg.uuid,
            )
        )
    logger.info(f"[LOAD HISTORY] Final message schemas: {message_schemas}")

    return ChatHistoryResponse(
        session_id=str(session_id),
        messages=message_schemas,
        total_messages=total_messages,
    )


def _to_session_read(session: Any) -> ChatSessionRead:
    """Convert ORM ChatSession to ChatSessionRead schema (avoids from_attributes config changes)."""
    return ChatSessionRead(
        uuid=session.uuid,
        user_id=session.user_id,
        title=session.title,
        is_active=session.is_active,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/sessions", response_model=List[ChatSessionRead])
async def get_user_chat_sessions(
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> List[ChatSessionRead]:
    """Get all chat sessions for the current user."""
    logger.info(f"DEBUG: Getting chat sessions for user: {get_user_uuid(current_user)}")
    
    # Get all active sessions for the current user
    sessions = await chat_session.get_by_user(db, user_id=get_user_uuid(current_user))
    logger.info(f"DEBUG: Found {len(sessions)} sessions for user")
    
    return [_to_session_read(s) for s in sessions]


@router.post("/sessions", response_model=ChatSessionRead)
async def create_new_chat_session(
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    title: Optional[str] = "New Chat",
) -> ChatSessionRead:
    """Create a new chat session for the current user."""
    logger.info(f"DEBUG: Creating new chat session for user: {get_user_uuid(current_user)}")
    
    session_create = ChatSessionCreate(
        user_id=get_user_uuid(current_user),
        title=title or "New Chat",
        is_active=True,
    )
    
    session = await chat_session.create(db, obj_in=session_create)
    logger.info(f"DEBUG: Created new session: {session.uuid}")
    return _to_session_read(session)


@router.put("/sessions/{session_id}/title")
@router.patch("/sessions/{session_id}/title")
async def update_chat_session_title(
    session_id: UUID,
    request: UpdateTitleRequest,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> ChatSessionRead:
    """Update the title of a chat session (PUT or PATCH)."""
    logger.info(f"DEBUG: Updating title for session: {session_id}")
    # Verify session belongs to current user
    session = await chat_session.get(db, uuid=session_id)
    if not session or session.user_id != get_user_uuid(current_user):
        logger.error(f"ERROR: Chat session not found or unauthorized: {session_id}")
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
    logger.info(f"DEBUG: Successfully updated session title: {session_id}")
    return _to_session_read(updated_session)


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: UUID,
    current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict:
    """Delete (deactivate) a chat session."""
    logger.info(f"DEBUG: Deleting session: {session_id}")
    
    # Verify session belongs to current user
    session = await chat_session.get(db, uuid=session_id)
    if not session or session.user_id != get_user_uuid(current_user):
        logger.error(f"ERROR: Chat session not found or unauthorized: {session_id}")
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
    
    logger.info(f"DEBUG: Successfully deleted session: {session_id}")
    return {"message": "Chat session deleted successfully", "session_id": str(session_id)}
