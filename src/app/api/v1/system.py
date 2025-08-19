from datetime import datetime

from fastapi import APIRouter

from ...core.config import settings
from ...schemas.chat import HealthResponse, ModelInfo

router = APIRouter(tags=["system"])


@router.get("/models", response_model=list[ModelInfo])
async def get_available_models() -> list[ModelInfo]:
    """Get list of available AI models."""

    # TODO: In production, this would query actual model availability
    # For now, return mock data
    models = [
        ModelInfo(
            id="gpt-4",
            name="GPT-4",
            type="text-generation",
            capabilities=["text-chat", "document-query", "code-generation"],
            is_available=True,
        ),
        ModelInfo(
            id="gpt-3.5-turbo",
            name="GPT-3.5 Turbo",
            type="text-generation",
            capabilities=["text-chat", "document-query"],
            is_available=True,
        ),
        ModelInfo(
            id="whisper-1",
            name="Whisper",
            type="speech-to-text",
            capabilities=["voice-transcription"],
            is_available=True,
        ),
        ModelInfo(
            id="tts-1",
            name="TTS-1",
            type="text-to-speech",
            capabilities=["voice-synthesis"],
            is_available=True,
        ),
        ModelInfo(
            id="claude-3",
            name="Claude 3",
            type="text-generation",
            capabilities=["text-chat", "document-query", "code-generation"],
            is_available=False,  # Coming soon
        ),
    ]

    return models


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""

    # TODO: In production, check actual service health
    # For now, return mock data
    services = {
        "database": "healthy",
        "ai_models": "healthy",
        "voice_processing": "healthy",
        "document_storage": "healthy",
        "authentication": "healthy",
    }

    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version=getattr(settings, "VERSION", "1.0.0"),
        services=services,
    )
