from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .admin.initialize import create_admin_interface
from .api import router
from .core.config import settings
from .core.setup import create_application, lifespan_factory

admin = create_admin_interface()


@asynccontextmanager
async def lifespan_with_admin(app: FastAPI) -> AsyncGenerator[None, None]:
    """Custom lifespan that includes admin initialization."""
    # Get the default lifespan
    default_lifespan = lifespan_factory(settings)

    # Run the default lifespan initialization and our admin initialization
    async with default_lifespan(app):
        # Initialize admin interface if it exists
        if admin:
            # Initialize admin database and setup
            await admin.initialize()

        yield


app = create_application(router=router, settings=settings, lifespan=lifespan_with_admin)

# --- START OF ROUTING FIX ---

# Define the path to the static directory
static_dir = Path("/code/static")

# Serve the main HTML pages for your frontend routes
# These need to be defined BEFORE the StaticFiles mount.
@app.get("/", response_class=FileResponse, tags=["Frontend"])
async def serve_home():
    """Serves the home page (index.html)."""
    return str(static_dir / "index.html")

@app.get("/login", response_class=FileResponse, tags=["Frontend"])
async def serve_login_page():
    """Serves the login page (login.html)."""
    return str(static_dir / "login.html")

@app.get("/chat", response_class=FileResponse, tags=["Frontend"])
async def serve_chat_page():
    """Serves the chat page (chat.html)."""
    return str(static_dir / "chat.html")

# Mount static files (CSS, JS)
# This handles all other files under /static
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# --- END OF ROUTING FIX ---


# Mount admin interface if enabled
if admin:
    app.mount(settings.CRUD_ADMIN_MOUNT_PATH, admin.app)

# Note: The original redirect and /index.html routes have been replaced by the code above.
# The API router (for /api/v1/...) is already included via `create_application`.
# The FastAPI app is now ready to serve both the API and the frontend.
