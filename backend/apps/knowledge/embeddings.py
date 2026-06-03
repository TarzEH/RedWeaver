"""OpenAI embeddings for the pgvector KB RAG."""
import os

EMBED_MODEL = "text-embedding-3-small"


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


def _client():
    key = _resolve_key()
    if not key:
        raise RuntimeError("No OpenAI API key available for embeddings")
    from openai import OpenAI

    return OpenAI(api_key=key, timeout=30)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts (batched)."""
    client = _client()
    out: list[list[float]] = []
    for i in range(0, len(texts), 100):
        batch = texts[i:i + 100]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        out.extend(d.embedding for d in resp.data)
    return out


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
