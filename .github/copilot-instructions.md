# Spek - Multimodal AI Platform - GitHub Copilot Instructions

## Project Overview

Spek is a multimodal AI platform built on FastAPI that provides text chat, voice processing, document analysis, and mobile automation capabilities. The project is based on a production-ready FastAPI boilerplate with extensive customizations for AI functionality.

## Core Architecture

### Technology Stack
- **Backend**: FastAPI (async/await) with Python 3.11+
- **Database**: PostgreSQL with SQLAlchemy 2.0 and Alembic migrations
- **AI Integration**: Google Gemini AI via `google-genai` library
- **Caching & Queues**: Redis for caching, job queues (ARQ), and rate limiting
- **Authentication**: JWT-based with refresh tokens and user tiers
- **Frontend**: Vanilla HTML/CSS/JavaScript (no framework)
- **Admin Panel**: CRUDAdmin for database management
- **Containerization**: Docker & Docker Compose
- **Background Tasks**: ARQ worker system with Redis
- **Security**: Rate limiting, CORS, secure token storage

### Project Structure
```
src/app/
├── main.py                 # FastAPI application entry point
├── api/                    # API layer with versioning
│   ├── dependencies.py     # Shared dependencies (auth, db)
│   └── v1/                 # API version 1 endpoints
│       ├── chat.py         # AI chat endpoints (Gemini integration)
│       ├── voice.py        # STT/TTS endpoints (mock implementation)
│       ├── documents.py    # Document upload/query endpoints
│       ├── users.py        # User management
│       ├── login.py        # Authentication
│       └── ...             # Other feature endpoints
├── core/                   # Core system functionality
│   ├── config.py           # Environment-based configuration
│   ├── setup.py            # Application factory and middleware
│   ├── security.py         # JWT and security utilities
│   ├── db/                 # Database configuration and models
│   ├── worker/             # Background task configuration
│   └── exceptions/         # Custom exception handlers
├── models/                 # SQLAlchemy database models
├── schemas/                # Pydantic request/response models
├── crud/                   # Database operations with FastCRUD
├── middleware/             # Custom middleware (caching, etc.)
└── services/               # Business logic services
```

## Development Guidelines

### Configuration Management
- All settings are centralized in `src/app/core/config.py`
- Environment variables loaded from `src/.env`
- Configuration classes use Pydantic for validation
- AI API key configured via `AI_API_KEY` or legacy `API_KEY`
- Multi-environment support (local, staging, production)

### Database Patterns
- Use SQLAlchemy 2.0 async patterns with `AsyncSession`
- Models inherit from base classes in `core/db/models.py`
- CRUD operations use FastCRUD for standardized patterns
- Database dependency: `async_get_db()` from `core/db/database.py`
- Migrations managed with Alembic in `src/migrations/`

### API Development
- All endpoints should be async and follow FastAPI patterns
- Use Pydantic schemas for request/response validation
- Include proper HTTP status codes and error handling
- Authentication required via `get_current_user` dependency
- API versioning under `/api/v1/` prefix
- Rate limiting applied via middleware

### AI Integration Patterns
- Gemini AI client initialized in `api/v1/chat.py`
- API key accessed via `settings.API_KEY.get_secret_value()`
- Chat history formatted for Gemini API requirements
- Long-running AI tasks should use background workers
- Error handling for AI service failures

### Authentication & Security
- JWT tokens with access/refresh pattern
- User roles and tiers for permission management
- Secure token storage in HTTP-only cookies
- Rate limiting on all endpoints
- Input validation with Pydantic schemas
- SQL injection protection via SQLAlchemy ORM

### Frontend Integration
- Static files served from `/static/` directory
- Main app logic in `static/js/main.js` with SpekApp class
- API client handles authentication headers automatically
- Frontend routes: `/` (home), `/login`, `/chat`
- No frontend framework - vanilla JavaScript

### Background Tasks
- ARQ worker system for async job processing
- Tasks defined in `core/worker/functions.py`
- Redis queue configuration in `core/worker/settings.py`
- Use for AI API calls, file processing, notifications

### Error Handling
- Custom exceptions in `core/exceptions/`
- Proper HTTP status codes for different error types
- Structured error responses with detail messages
- Logging configuration in `core/logger.py`

## Code Patterns & Conventions

### Dependency Injection
```python
# Standard endpoint pattern
@router.post("/endpoint")
async def endpoint_function(
    request: RequestSchema,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> ResponseSchema:
```

### CRUD Operations
```python
# Use FastCRUD for database operations
from crud.crud_model import model_crud
result = await model_crud.create(db, obj_in=create_data, user_id=user.uuid)
```

### AI Service Integration
```python
# Gemini AI client pattern
client = genai.Client(api_key=settings.API_KEY.get_secret_value())
response = await client.models.generate_content(
    model="gemini-1.5-flash",
    contents=[{"role": "user", "parts": [{"text": message}]}]
)
```

### Configuration Access
```python
# Settings access pattern
from core.config import settings
database_url = settings.POSTGRES_URL
ai_key = settings.API_KEY.get_secret_value()
```

## Key Features Implementation

### Chat System
- Real-time text chat with Gemini AI
- Chat session and message persistence
- History management and context handling
- WebSocket support for streaming responses

### Voice Processing
- Speech-to-text (STT) endpoints (currently mocked)
- Text-to-speech (TTS) endpoints (currently mocked)
- Audio file upload and processing
- Language detection and confidence scoring

### Document Analysis
- File upload with size and type validation
- Document parsing and content extraction
- Query-based document search
- Support for multiple file formats

### User Management
- Multi-tier user system (free, premium, enterprise)
- JWT-based authentication with refresh tokens
- User profile management
- Admin panel integration

## Docker & Deployment

### Development Setup
```bash
# Start all services
docker compose up -d --build

# View logs
docker compose logs -f web

# Access services
# API: http://localhost:8000
# Admin: http://localhost:8000/admin
# Frontend: http://localhost:8000/
```

### Environment Configuration
- Development: `ENVIRONMENT=local`
- Staging: `ENVIRONMENT=staging` 
- Production: `ENVIRONMENT=production`
- Docs disabled in production environment

## Testing Patterns

### Test Structure
- Unit tests in `tests/` directory
- Fixtures in `tests/conftest.py`
- Mock external dependencies (AI APIs, Redis)
- Test database isolation per test

### Test Examples
```python
# API endpoint testing
async def test_chat_endpoint(async_client, test_user_token):
    response = await async_client.post(
        "/api/v1/chat/text",
        json={"message": "Hello"},
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == 200
```

## Performance Considerations

### Async Patterns
- All database operations should be async
- Use connection pooling for database access
- Redis for caching frequently accessed data
- Background tasks for long-running operations

### Caching Strategy
- Redis for session data and temporary storage
- Client-side caching headers via middleware
- Database query optimization with proper indexes

### Scaling Considerations
- Horizontal scaling with multiple worker processes
- Redis cluster for high availability
- Database read replicas for read-heavy workloads
- CDN for static file serving

## Common Tasks

### Adding New API Endpoints
1. Create endpoint in appropriate `api/v1/` file
2. Define Pydantic schemas in `schemas/`
3. Add database models if needed in `models/`
4. Implement CRUD operations in `crud/`
5. Add authentication and rate limiting
6. Write tests in `tests/`

### Adding AI Features
1. Extend AI client configuration in `chat.py`
2. Add new schemas for request/response
3. Implement background tasks for long operations
4. Handle API failures gracefully
5. Add proper logging and monitoring

### Database Changes
1. Create new models in `models/`
2. Generate migration: `alembic revision --autogenerate`
3. Review and edit migration file
4. Apply migration: `alembic upgrade head`
5. Update CRUD operations accordingly

## Security Best Practices

- Never log sensitive data (API keys, passwords)
- Validate all input with Pydantic schemas
- Use parameterized queries (SQLAlchemy handles this)
- Implement proper rate limiting
- Secure cookie configuration for tokens
- Regular dependency updates for security patches

## Monitoring & Logging

- Structured logging with proper log levels
- Health check endpoints for monitoring
- Redis connection monitoring
- Database performance metrics
- AI API usage tracking

Remember: This is a production-ready application with emphasis on async operations, proper error handling, security, and scalability. Follow established patterns and maintain consistency with the existing codebase.
