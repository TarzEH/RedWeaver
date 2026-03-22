"""Settings (API keys, provider config, Ollama integration, dynamic model listing)."""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.keys import KeysUpdate, KeysStatus
from app.core.deps import get_keys_service
from app.services.keys_service import KeysService

router = APIRouter()

_VALID_PROVIDERS = {"openai", "anthropic", "google", "ollama", ""}


@router.post("/api/settings/keys", response_model=KeysStatus)
def update_keys(body: KeysUpdate, keys_service: KeysService = Depends(get_keys_service)):
    """Store API keys and provider settings. Set clear=true to clear all."""
    if body.model_provider and body.model_provider not in _VALID_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"Invalid model_provider: {body.model_provider}")
    return keys_service.update_keys(body)


@router.get("/api/settings/keys", response_model=KeysStatus)
def get_keys_status(keys_service: KeysService = Depends(get_keys_service)):
    """Return provider configuration status (booleans + active settings)."""
    return keys_service.get_status()


# ------------------------------------------------------------------ #
# Dynamic model listing (OpenAI, Anthropic, Ollama)
# ------------------------------------------------------------------ #

@router.get("/api/settings/models/openai")
async def get_openai_models(keys_service: KeysService = Depends(get_keys_service)):
    """Fetch available models from the OpenAI API."""
    api_key = keys_service.resolve_openai_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            import re

            # Include any GPT chat model or reasoning model (o-series)
            chat_prefixes = ("gpt-", "o1", "o3", "o4")
            # Exclude non-chat variants
            exclude_keywords = (
                "-audio", "-tts", "-transcribe", "-realtime",
                "-search", "-instruct", "-diarize", "-codex",
                "chat-latest", "gpt-image",
            )
            # Exclude date-stamped versions (YYYY-MM-DD or legacy MMDD/MMYY)
            date_pattern = re.compile(r"-\d{4}(-\d{2}-\d{2})?$")
            # But keep models ending in known non-date suffixes
            keep_suffixes = ("-mini", "-nano", "-pro", "-turbo", "-preview", "-16k")

            models = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                if not any(mid.startswith(p) for p in chat_prefixes):
                    continue
                if any(ex in mid for ex in exclude_keywords):
                    continue
                # Skip date-stamped versions unless they end with a known suffix
                if date_pattern.search(mid) and not any(mid.endswith(s) for s in keep_suffixes):
                    continue
                models.append({"id": mid, "name": mid})
            models.sort(key=lambda x: x["id"], reverse=True)
            return {"models": models, "provider": "openai"}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="OpenAI API error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/settings/models/anthropic")
async def get_anthropic_models(keys_service: KeysService = Depends(get_keys_service)):
    """Fetch available Anthropic models from their API, fallback to curated list."""
    api_key = keys_service.resolve_anthropic_key()
    configured = bool(api_key)

    # Curated fallback (used when key not configured or API call fails)
    fallback = [
        {"id": "claude-sonnet-4-6-20260218", "name": "Claude Sonnet 4.6"},
        {"id": "claude-opus-4-6-20260204", "name": "Claude Opus 4.6"},
        {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5"},
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
        {"id": "claude-opus-4-20250514", "name": "Claude Opus 4"},
    ]

    if not api_key:
        return {"models": fallback, "provider": "anthropic", "configured": False}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                name = m.get("display_name", mid)
                models.append({"id": mid, "name": name})
            models.sort(key=lambda x: x["id"], reverse=True)
            if models:
                return {"models": models, "provider": "anthropic", "configured": True}
    except Exception:
        pass  # Fall through to curated list

    return {"models": fallback, "provider": "anthropic", "configured": configured}


# ------------------------------------------------------------------ #
# Google Gemini
# ------------------------------------------------------------------ #

@router.get("/api/settings/models/google")
async def get_google_models(keys_service: KeysService = Depends(get_keys_service)):
    """Fetch available models from the Google Gemini API."""
    api_key = keys_service.resolve_google_key()
    configured = bool(api_key)

    fallback = [
        {"id": "gemini-3.1-pro", "name": "Gemini 3.1 Pro"},
        {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite"},
        {"id": "gemini-3-flash", "name": "Gemini 3 Flash"},
        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro"},
        {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
    ]

    if not api_key:
        return {"models": fallback, "provider": "google", "configured": False}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            )
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                mid = m.get("name", "").replace("models/", "")
                display = m.get("displayName", mid)
                methods = m.get("supportedGenerationMethods", [])
                if "gemini" in mid.lower() and "generateContent" in methods:
                    models.append({"id": mid, "name": display})
            models.sort(key=lambda x: x["id"], reverse=True)
            if models:
                return {"models": models, "provider": "google", "configured": True}
    except Exception:
        pass

    return {"models": fallback, "provider": "google", "configured": configured}


# ------------------------------------------------------------------ #
# Ollama endpoints (accept optional ?url= override for testing)
# ------------------------------------------------------------------ #

@router.get("/api/settings/ollama/models")
async def get_ollama_models(
    url: str | None = Query(None),
    keys_service: KeysService = Depends(get_keys_service),
):
    """Fetch available models from the Ollama instance."""
    from app.repositories.api_keys_repository import DEFAULT_OLLAMA_BASE_URL

    base_url = (url or keys_service.resolve_ollama_url() or DEFAULT_OLLAMA_BASE_URL).rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                models.append({
                    "name": m.get("name", ""),
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                })
            # Sort by most recently modified first
            models.sort(key=lambda x: x.get("modified_at", ""), reverse=True)
            return {"models": models, "base_url": base_url}
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot connect to Ollama. Is it running?")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Ollama API error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/settings/ollama/health")
async def check_ollama_health(
    url: str | None = Query(None),
    keys_service: KeysService = Depends(get_keys_service),
):
    """Check if Ollama is reachable. Accepts optional ?url= to test before saving."""
    from app.repositories.api_keys_repository import DEFAULT_OLLAMA_BASE_URL

    base_url = (url or keys_service.resolve_ollama_url() or DEFAULT_OLLAMA_BASE_URL).rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            return {"status": "connected", "base_url": base_url}
    except Exception:
        return {"status": "disconnected", "base_url": base_url}
