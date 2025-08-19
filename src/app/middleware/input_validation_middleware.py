import json
import re
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate and sanitize input to prevent injection attacks."""

    # Patterns that indicate potential injection attempts
    SUSPICIOUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS
        r'javascript:',  # XSS
        r'on\w+\s*=',  # Event handlers
        r'(union|select|insert|update|delete|drop|exec|execute)\s+',  # SQL injection
        r'(\'\s*(or|and)\s*\'|\'\s*;\s*)',  # SQL injection
        r'(<|>|&lt;|&gt;)',  # HTML tags
        r'{{.*?}}',  # Template injection
        r'<%.*?%>',  # Template injection
    ]

    def __init__(self, app):
        super().__init__(app)
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SUSPICIOUS_PATTERNS]

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Skip validation for certain endpoints
        if self._should_skip_validation(request):
            return await call_next(request)

        # Validate query parameters
        for key, value in request.query_params.items():
            if self._contains_suspicious_content(value):
                raise HTTPException(status_code=400, detail=f"Invalid input in query parameter: {key}")

        # Validate request body for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await self._get_request_body(request)
            if body and self._validate_request_body(body):
                raise HTTPException(status_code=400, detail="Invalid input in request body")

        return await call_next(request)

    def _should_skip_validation(self, request: Request) -> bool:
        """Skip validation for certain endpoints that need raw content."""
        skip_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static/",
            "/admin/",
        ]
        return any(request.url.path.startswith(path) for path in skip_paths)

    def _contains_suspicious_content(self, content: str) -> bool:
        """Check if content contains suspicious patterns."""
        if not isinstance(content, str):
            return False

        for pattern in self.compiled_patterns:
            if pattern.search(content):
                return True
        return False

    async def _get_request_body(self, request: Request) -> dict | None:
        """Safely get request body."""
        try:
            if "application/json" in request.headers.get("content-type", ""):
                body = await request.body()
                if body:
                    return json.loads(body)
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _validate_request_body(self, body: dict) -> bool:
        """Validate request body recursively."""
        if isinstance(body, dict):
            for key, value in body.items():
                if isinstance(value, str) and self._contains_suspicious_content(value):
                    return True
                elif isinstance(value, dict | list):
                    if self._validate_request_body(value):
                        return True
        elif isinstance(body, list):
            for item in body:
                if self._validate_request_body(item):
                    return True
        elif isinstance(body, str):
            return self._contains_suspicious_content(body)

        return False
