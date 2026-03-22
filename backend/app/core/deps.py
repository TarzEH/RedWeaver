"""FastAPI dependency injection: bind repositories, services, and crew factory."""

import os
from functools import lru_cache
from typing import Any

import redis

from app.core.event_bus import event_bus
from app.core.llm_factory import LLMFactory
from app.core.crew_factory_provider import build_crew_factory as _build_crew_factory
from app.crews.bug_hunt.builder import CrewFactory
from app.repositories.api_keys_repository import ApiKeysRepositoryProtocol
from app.repositories.huntflow_repository import HuntflowRepositoryProtocol
from app.repositories.run_repository import RunRepositoryProtocol
from app.repositories.redis_run_repository import RedisRunRepository
from app.repositories.redis_huntflow_repository import RedisHuntflowRepository
from app.repositories.redis_api_keys_repository import RedisApiKeysRepository
from app.repositories.redis_user_repository import RedisUserRepository
from app.repositories.redis_hunt_repository import RedisHuntRepository
from app.repositories.redis_finding_repository import RedisFindingRepository
from app.repositories.redis_workspace_repository import RedisWorkspaceRepository
from app.repositories.redis_session_repository import RedisSessionRepository
from app.repositories.redis_target_repository import RedisTargetRepository
from app.services.chat_service import ChatService
from app.services.auth_service import AuthService
from app.services.finding_service import FindingService
from app.services.hunt_service import HuntService
from app.services.workspace_service import WorkspaceService
from app.services.session_service import SessionService
from app.services.target_service import TargetService
from app.services.hunt_execution_service import HuntExecutionService
from app.services.keys_service import KeysService
from app.services.run_service import RunService
from app.services.tool_service import ToolService
from app.tools.registry import ToolRegistry


# ------------------------------------------------------------------ #
# Redis client singleton
# ------------------------------------------------------------------ #

@lru_cache
def _get_redis_client() -> redis.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6380/0")
    return redis.Redis.from_url(url, decode_responses=True)


# ------------------------------------------------------------------ #
# Repository singletons (Redis-backed)
# ------------------------------------------------------------------ #

@lru_cache
def get_run_repository() -> RunRepositoryProtocol:
    return RedisRunRepository(_get_redis_client())


@lru_cache
def get_api_keys_repository() -> ApiKeysRepositoryProtocol:
    return RedisApiKeysRepository(_get_redis_client())


@lru_cache
def get_huntflow_repository() -> HuntflowRepositoryProtocol:
    return RedisHuntflowRepository(_get_redis_client())


@lru_cache
def get_finding_repository() -> RedisFindingRepository:
    return RedisFindingRepository(_get_redis_client())


@lru_cache
def get_user_repository() -> RedisUserRepository:
    return RedisUserRepository(_get_redis_client())


def get_auth_service() -> AuthService:
    return AuthService(user_repo=get_user_repository())


@lru_cache
def get_hunt_repository() -> RedisHuntRepository:
    return RedisHuntRepository(_get_redis_client())


def get_hunt_service() -> HuntService:
    return HuntService(
        hunt_repo=get_hunt_repository(),
        session_service=get_session_service(),
        run_repo=get_run_repository(),
    )


def get_finding_service() -> FindingService:
    return FindingService(finding_repo=get_finding_repository())


@lru_cache
def get_workspace_repository() -> RedisWorkspaceRepository:
    return RedisWorkspaceRepository(_get_redis_client())


@lru_cache
def get_session_repository() -> RedisSessionRepository:
    return RedisSessionRepository(_get_redis_client())


@lru_cache
def get_target_repository() -> RedisTargetRepository:
    return RedisTargetRepository(_get_redis_client())


def get_workspace_service() -> WorkspaceService:
    return WorkspaceService(workspace_repo=get_workspace_repository())


def get_session_service() -> SessionService:
    return SessionService(session_repo=get_session_repository())


def get_target_service() -> TargetService:
    return TargetService(target_repo=get_target_repository())


# ------------------------------------------------------------------ #
# LLM configuration
# ------------------------------------------------------------------ #

def get_llm_factory(api_keys_repository: ApiKeysRepositoryProtocol | None = None) -> LLMFactory:
    repo = api_keys_repository or get_api_keys_repository()
    return LLMFactory(repo)


# ------------------------------------------------------------------ #
# Tool registry
# ------------------------------------------------------------------ #

def get_tool_registry(api_keys_repository: ApiKeysRepositoryProtocol | None = None) -> ToolRegistry:
    repo = api_keys_repository or get_api_keys_repository()
    keys = repo.get_all()
    return ToolRegistry(
        virustotal_api_key=keys.get("virustotal_api_key"),
        urlscan_api_key=keys.get("urlscan_api_key"),
    )


# ------------------------------------------------------------------ #
# CrewAI factory
# ------------------------------------------------------------------ #

def get_crew_factory(
    api_keys_repository: ApiKeysRepositoryProtocol | None = None,
) -> CrewFactory | None:
    """Build the CrewAI factory with model, tool, and memory configuration."""
    keys_repo = api_keys_repository or get_api_keys_repository()
    return _build_crew_factory(keys_repo)


# ------------------------------------------------------------------ #
# Services
# ------------------------------------------------------------------ #

def get_hunt_execution_service() -> HuntExecutionService:
    return HuntExecutionService(
        run_repository=get_run_repository(),
        huntflow_repository=get_huntflow_repository(),
        api_keys_repository=get_api_keys_repository(),
        event_bus=event_bus,
    )


def get_run_service(run_repository=None) -> RunService:
    repo = run_repository or get_run_repository()
    return RunService(run_repository=repo)


def get_keys_service(api_keys_repository=None) -> KeysService:
    repo = api_keys_repository or get_api_keys_repository()
    return KeysService(api_keys_repository=repo)


def get_tool_service(api_keys_repository=None) -> ToolService:
    registry = get_tool_registry(api_keys_repository)
    return ToolService(tool_registry=registry)


def get_chat_service(run_repository=None, api_keys_repository=None) -> ChatService:
    run_repo = run_repository or get_run_repository()
    keys_repo = api_keys_repository or get_api_keys_repository()
    # ChatService needs to know if an agent is available for scan intent detection
    crew_factory = get_crew_factory(keys_repo)
    return ChatService(
        run_repository=run_repo,
        api_keys_repository=keys_repo,
        hunt_graph=crew_factory,  # Passes factory (truthy if API key set)
    )
