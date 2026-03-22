"""
RedWeaver backend - FastAPI app.
Multi-agent bug-hunting automation with SSE streaming.
"""
import asyncio
import os
import warnings

# Suppress pydantic V2 deprecation warnings from crewai internals
warnings.filterwarnings("ignore", message=".*Valid config keys have changed.*", category=UserWarning)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, tools, graph, runs, settings, chat, stream, findings, reports, huntflow
from app.api import auth, workspaces, sessions, targets, hunts, knowledge
from app.api.middleware.correlation import CorrelationMiddleware
from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.core.event_bus import event_bus
from app.core.logging_config import configure_logging

# Configure structured logging before anything else
configure_logging(os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="RedWeaver",
    description="Multi-agent bug-hunting automation",
    version="0.3.0",
)

# Middleware (order matters: outermost first)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(CorrelationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _bind_event_loop() -> None:
    """Bind the main event loop to the EventBus so background threads can
    safely push events onto asyncio.Queues via call_soon_threadsafe."""
    event_bus.set_loop(asyncio.get_running_loop())


@app.on_event("startup")
async def _seed_default_user() -> None:
    """Create default user on first boot so the app is usable immediately."""
    import logging
    from app.core.deps import get_user_repository
    from app.core.security import hash_password
    from app.domain.user import User, UserRole

    log = logging.getLogger("redweaver.seed")
    repo = get_user_repository()

    # Only create if no users exist yet
    if repo.get_by_email("admin@redweaver.io"):
        return

    default_user = User(
        email="admin@redweaver.io",
        username="redweaver",
        hashed_password=hash_password("redweaver"),
        role=UserRole.ADMIN,
    )
    try:
        repo.create(default_user)
        log.info(
            "Seeded demo admin user (first boot only). Credentials are documented in README; "
            "change the password before any non-local deployment."
        )
    except Exception as e:
        log.warning("Could not seed default user: %s", e)


app.include_router(health.router)
app.include_router(tools.router)
app.include_router(graph.router)
app.include_router(runs.router)
app.include_router(settings.router)
app.include_router(chat.router)
app.include_router(stream.router)
app.include_router(findings.router)
app.include_router(reports.router)
app.include_router(huntflow.router)
app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(sessions.router)
app.include_router(targets.router)
app.include_router(hunts.router)
app.include_router(knowledge.router)
