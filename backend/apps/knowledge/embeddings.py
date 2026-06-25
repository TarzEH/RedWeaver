"""Embeddings for the pgvector KB RAG.

Pluggable provider. The active provider/model is resolved **UI-first**: a global
``KbEmbeddingConfig`` row (edited from the Settings page) wins, falling back to
``settings`` / env vars when no row exists yet.

* ``openai``      -- OpenAI ``text-embedding-3-small`` (1536 dims, needs a key).
* ``huggingface`` -- a local sentence-transformers model via the LangChain SDK
  (``langchain_huggingface``). Runs **fully offline** once the model is cached,
  needs no API key, and writes straight into pgvector -- no Chroma required.

Local models are loaded once per (model, device) and reused (loading is slow).
"""
import os
import threading

from django.conf import settings

# OpenAI default model.
EMBED_MODEL = "text-embedding-3-small"

# Default local model when provider=huggingface and no model is set.
# all-MiniLM-L6-v2: 384 dims, ~80 MB, needs no query/passage instruction prefix.
DEFAULT_HF_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_hf_lock = threading.Lock()
_hf_cache: dict = {}  # (model, device) -> langchain HuggingFaceEmbeddings


def active_config() -> dict:
    """Resolve the active embedding config: DB singleton first, then env/settings.

    Returns ``{provider, model, dim, device}`` with provider defaults applied to
    a blank model.
    """
    provider = getattr(settings, "KB_EMBED_PROVIDER", "openai")
    model = getattr(settings, "KB_EMBED_MODEL", "")
    dim = int(getattr(settings, "KB_EMBED_DIM", 1536))
    device = getattr(settings, "KB_EMBED_DEVICE", "cpu")
    try:
        from .models import KbEmbeddingConfig

        cfg = KbEmbeddingConfig.objects.filter(id=KbEmbeddingConfig.SINGLETON_ID).first()
        if cfg:
            provider, model, dim, device = cfg.provider, cfg.model, cfg.dimension, cfg.device
    except Exception:
        # DB not migrated yet / table missing — fall back to env.
        pass

    provider = (provider or "openai").lower()
    if not model:
        model = DEFAULT_HF_MODEL if provider == "huggingface" else EMBED_MODEL
    return {"provider": provider, "model": model, "dim": int(dim or 1536), "device": device or "cpu"}


# ---------------------------------------------------------------------------
# OpenAI path
# ---------------------------------------------------------------------------
def _resolve_key() -> str:
    """Prefer a user-set vault key (UI-first), fall back to env."""
    try:
        from apps.accounts.models import ApiKeyVault

        v = ApiKeyVault.objects.exclude(openai_api_key="").first()
        if v and v.openai_api_key:
            return v.openai_api_key
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY", "").strip()


def _openai_client():
    key = _resolve_key()
    if not key:
        raise RuntimeError("No OpenAI API key available for embeddings")
    from openai import OpenAI

    return OpenAI(api_key=key, timeout=30)


def _openai_embed(texts: list[str], model: str) -> list[list[float]]:
    client = _openai_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), 100):
        batch = texts[i:i + 100]
        resp = client.embeddings.create(model=model, input=batch)
        out.extend(d.embedding for d in resp.data)
    return out


# ---------------------------------------------------------------------------
# HuggingFace offline path (LangChain SDK)
# ---------------------------------------------------------------------------
def _get_hf_embedder(model: str, device: str):
    """Lazily build and cache a local LangChain HuggingFace embedder."""
    cache_key = (model, device)
    emb = _hf_cache.get(cache_key)
    if emb is None:
        with _hf_lock:
            emb = _hf_cache.get(cache_key)
            if emb is None:
                from langchain_huggingface import HuggingFaceEmbeddings

                emb = HuggingFaceEmbeddings(
                    model_name=model,
                    model_kwargs={"device": device},
                    # Cosine retrieval (vector_cosine_ops) wants unit-norm vectors.
                    encode_kwargs={"normalize_embeddings": True},
                )
                _hf_cache[cache_key] = emb
    return emb


# ---------------------------------------------------------------------------
# Public API (stable signatures used by ingest + search)
# ---------------------------------------------------------------------------
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts (batched) using the active provider."""
    texts = list(texts)
    if not texts:
        return []
    cfg = active_config()
    if cfg["provider"] == "huggingface":
        return _get_hf_embedder(cfg["model"], cfg["device"]).embed_documents(texts)
    return _openai_embed(texts, cfg["model"])


def embed_query(query: str) -> list[float]:
    cfg = active_config()
    if cfg["provider"] == "huggingface":
        return _get_hf_embedder(cfg["model"], cfg["device"]).embed_query(query)
    return _openai_embed([query], cfg["model"])[0]


def probe_dimension() -> int:
    """Return the embedding dimension of the active provider/model by embedding a
    tiny probe. Used by re-index to size the pgvector column automatically."""
    return len(embed_query("dimension probe"))


def get_langchain_embeddings():
    """Return a LangChain ``Embeddings`` object matching the active KB config.

    Used by the Ragas evaluation harness (which needs a LangChain embeddings
    instance to wrap). For HuggingFace this reuses the same cached local model
    that ingestion/search use; for OpenAI it builds ``OpenAIEmbeddings`` with the
    same model + resolved key.
    """
    cfg = active_config()
    if cfg["provider"] == "huggingface":
        return _get_hf_embedder(cfg["model"], cfg["device"])
    from langchain_openai import OpenAIEmbeddings

    key = _resolve_key()
    if not key:
        raise RuntimeError("No OpenAI API key available for embeddings")
    return OpenAIEmbeddings(model=cfg["model"], api_key=key)
