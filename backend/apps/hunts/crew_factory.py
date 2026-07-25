"""Build a CrewFactory from a KeysProvider (port of legacy crew_factory_provider)."""
from __future__ import annotations

import logging
from typing import Any

from redweaver_engine.model_routing import Routing, load_routing

logger = logging.getLogger(__name__)


def build_embedder_config(llm_factory, keys: dict) -> dict | None:
    provider = llm_factory._resolve_provider(keys)
    if provider == "openai":
        api_key = llm_factory._resolve_openai_key(keys)
        if api_key:
            return {"provider": "openai",
                    "config": {"model": "text-embedding-3-small", "api_key": api_key}}
    elif provider == "google":
        api_key = llm_factory._resolve_google_key(keys)
        if api_key:
            return {"provider": "google",
                    "config": {"model": "models/text-embedding-004", "api_key": api_key}}
    elif provider == "ollama":
        url = llm_factory._resolve_ollama_url(keys) or llm_factory.DEFAULT_OLLAMA_URL
        return {"provider": "ollama",
                "config": {"model": "nomic-embed-text", "url": url}}
    return None


def resolve_model_selection(
    llm_factory,
    keys: dict,
    provider: str = "",
    model: str = "",
) -> tuple[str, str]:
    """Resolve the (provider, model) pair an LLM should be built with.

    With no routing override this must return exactly what the pre-routing code
    returned — the globally resolved provider and the user's selected model.
    The provider default is consulted *only* when routing explicitly asked for a
    provider without naming a model, because the globally selected model may not
    exist on that other provider.
    """
    requested_provider = (provider or "").strip()
    resolved_provider = requested_provider or llm_factory._resolve_provider(keys)

    if model:
        return resolved_provider, model
    if requested_provider:
        fallback = llm_factory.DEFAULT_MODELS.get(requested_provider)
        if fallback:
            return resolved_provider, fallback
    return resolved_provider, llm_factory.resolve_model_name()


def _build_crewai_llm(
    llm_factory,
    keys: dict,
    provider: str = "",
    model: str = "",
    temperature: float = 0.1,
):
    """Build a crewai.LLM (litellm) — crewai 1.x rejects LangChain chat models.

    Uses litellm provider-prefixed model strings and the resolved API key.
    ``provider`` / ``model`` override the globally resolved selection; both are
    empty for the default LLM, which keeps the pre-routing behaviour exactly.
    """
    from crewai import LLM

    provider, model = resolve_model_selection(llm_factory, keys, provider, model)

    if provider == "anthropic":
        return LLM(model=f"anthropic/{model}",
                   api_key=llm_factory._resolve_anthropic_key(keys), temperature=temperature)
    if provider == "google":
        return LLM(model=f"gemini/{model}",
                   api_key=llm_factory._resolve_google_key(keys), temperature=temperature)
    if provider == "ollama":
        url = llm_factory._resolve_ollama_url(keys) or llm_factory.DEFAULT_OLLAMA_URL
        return LLM(model=f"ollama/{model}", base_url=url, temperature=temperature)
    return LLM(model=model, api_key=llm_factory._resolve_openai_key(keys), temperature=temperature)


class AgentLLMResolver:
    """Hands out one crewai.LLM per agent according to the routing table.

    Agents with no routing override share the single default LLM object, so an
    unconfigured install builds exactly one LLM — same as before routing existed.
    """

    def __init__(self, llm_factory, keys: dict, routing: Routing, default_llm: Any) -> None:
        self._llm_factory = llm_factory
        self._keys = keys
        self._routing = routing
        self._default = default_llm
        self._cache: dict[tuple[str, str, float], Any] = {}

    @property
    def default_llm(self) -> Any:
        return self._default

    def for_agent(self, agent_name: str) -> Any:
        spec = self._routing.spec_for(agent_name)
        if not spec.is_override:
            return self._default

        temperature = 0.1 if spec.temperature is None else spec.temperature
        key = (spec.provider, spec.model, temperature)
        if key not in self._cache:
            try:
                self._cache[key] = _build_crewai_llm(
                    self._llm_factory,
                    self._keys,
                    provider=spec.provider,
                    model=spec.model,
                    temperature=temperature,
                )
                logger.info(
                    "Agent %r routed to tier=%s provider=%s model=%s",
                    agent_name, spec.tier, spec.provider or "<global>", spec.model or "<global>",
                )
            except Exception:
                # A bad per-tier override must never take a hunt down; the agent
                # falls back to the default LLM and the run continues.
                logger.warning(
                    "Failed to build routed LLM for agent %r (tier=%s, provider=%s, model=%s); "
                    "falling back to the default model",
                    agent_name, spec.tier, spec.provider, spec.model, exc_info=True,
                )
                self._cache[key] = self._default
        return self._cache[key]


def build_llm_resolver(keys_provider) -> AgentLLMResolver | None:
    """Return an AgentLLMResolver, or None if no LLM key is configured."""
    from redweaver_engine.llm_factory import LLMFactory

    llm_factory = LLMFactory(keys_provider)
    if not llm_factory.has_api_key():
        return None

    keys = keys_provider.get_all()
    routing = load_routing(keys=keys)
    default_llm = _build_crewai_llm(llm_factory, keys)

    if routing.is_active:
        logger.info("Model routing active: %s", routing.describe())
    else:
        logger.debug("Model routing inactive — all agents use the globally selected model")

    return AgentLLMResolver(llm_factory, keys, routing, default_llm)


def llm_for_role(llm_factory, keys: dict, role: str):
    """Build the LLM for a single non-crew role (``attack``, ``verifier``, ...).

    Falls back to the globally selected model when the role has no override,
    which is the shipped default.
    """
    spec = load_routing(keys=keys).spec_for(role)
    if not spec.is_override:
        return _build_crewai_llm(llm_factory, keys)
    try:
        llm = _build_crewai_llm(
            llm_factory,
            keys,
            provider=spec.provider,
            model=spec.model,
            temperature=0.1 if spec.temperature is None else spec.temperature,
        )
        logger.info(
            "Role %r routed to tier=%s provider=%s model=%s",
            role, spec.tier, spec.provider or "<global>", spec.model or "<global>",
        )
        return llm
    except Exception:
        logger.warning(
            "Failed to build routed LLM for role %r; using the default model", role, exc_info=True
        )
        return _build_crewai_llm(llm_factory, keys)


def build_crew_factory(keys_provider) -> Any | None:
    """Return a CrewFactory, or None if no LLM key is configured."""
    from redweaver_engine.crews.bug_hunt.builder import CrewFactory
    from redweaver_engine.llm_factory import LLMFactory
    from redweaver_engine.tools.registry import ToolRegistry

    resolver = build_llm_resolver(keys_provider)
    if resolver is None:
        return None

    keys = keys_provider.get_all()
    llm_factory = LLMFactory(keys_provider)
    registry = ToolRegistry(
        virustotal_api_key=keys.get("virustotal_api_key"),
        urlscan_api_key=keys.get("urlscan_api_key"),
    )
    embedder = build_embedder_config(llm_factory, keys)
    return CrewFactory(
        tool_registry=registry,
        llm=resolver.default_llm,
        embedder_config=embedder,
        llm_for_agent=resolver.for_agent,
    )
