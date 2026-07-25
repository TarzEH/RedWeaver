"""Per-agent model routing: which LLM each agent role runs on.

Pure resolution logic — no Django, no crewai, no network. The routing table is
declared in ``config/model_routing.yaml`` and can be overridden per tier or per
agent from the environment or the user's key vault.

Routing is **inactive by default**: with the shipped config every tier resolves
to an empty model, and callers fall back to the globally selected model. No
provider (least of all a local one like Ollama) is ever selected implicitly —
a provider is used only when it is named explicitly in the config, the
environment, or the vault.

    routing = load_routing(keys=vault.get_all())
    spec = routing.spec_for("recon")      # TierSpec(model=..., provider=...)
    if not spec.model:
        ...                               # caller uses its global model
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "model_routing.yaml"

VALID_PROVIDERS = ("openai", "anthropic", "google", "ollama")

#: Used when the config file is missing or unreadable. Mirrors the shipped YAML:
#: every tier empty, so the caller keeps using its global model.
FALLBACK_CONFIG: dict[str, Any] = {
    "tiers": {
        "fast": {"model": "", "provider": "", "temperature": 0.1},
        "standard": {"model": "", "provider": "", "temperature": 0.1},
        "deep": {"model": "", "provider": "", "temperature": 0.1},
    },
    "default_tier": "standard",
    "agents": {},
}


@dataclass(frozen=True)
class TierSpec:
    """A resolved routing decision for one agent.

    ``model`` / ``provider`` are empty when nothing was configured, which the
    caller must read as "use the global selection".
    """

    agent: str
    tier: str
    model: str = ""
    provider: str = ""
    temperature: float | None = None

    @property
    def is_override(self) -> bool:
        """True when this agent should deviate from the global LLM."""
        return bool(self.model or self.provider)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _parse_config_text(text: str) -> Any:
    try:
        import yaml
    except ImportError:  # pragma: no cover - yaml is a hard dependency in prod
        return json.loads(text)
    return yaml.safe_load(text)


@lru_cache(maxsize=1)
def load_config_file() -> dict[str, Any]:
    """Read ``config/model_routing.yaml``; fall back to an inert config."""
    try:
        data = _parse_config_text(_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.debug("model_routing.yaml not found at %s; routing inactive", _CONFIG_PATH)
        return dict(FALLBACK_CONFIG)
    except Exception:
        logger.warning("model_routing.yaml is unreadable; routing inactive", exc_info=True)
        return dict(FALLBACK_CONFIG)
    if not isinstance(data, dict):
        logger.warning("model_routing.yaml must be a mapping; routing inactive")
        return dict(FALLBACK_CONFIG)
    return data


class Routing:
    """Resolves ``agent name -> TierSpec`` from config + env + vault keys."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        env: Mapping[str, str] | None = None,
        keys: Mapping[str, Any] | None = None,
    ) -> None:
        self._config: Mapping[str, Any] = config if config is not None else load_config_file()
        self._env: Mapping[str, str] = env if env is not None else os.environ
        self._keys: Mapping[str, Any] = keys or {}

        tiers = self._config.get("tiers")
        self._tiers: dict[str, Any] = tiers if isinstance(tiers, dict) else {}
        agents = self._config.get("agents")
        self._agents: dict[str, Any] = agents if isinstance(agents, dict) else {}
        self._default_tier = _clean(self._config.get("default_tier")) or "standard"

    # ------------------------------------------------------------------
    # Enablement
    # ------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        """False when MODEL_ROUTING_ENABLED is set to a falsy value."""
        raw = _clean(self._env.get("MODEL_ROUTING_ENABLED"))
        if not raw:
            return True
        return raw.lower() in ("1", "true", "yes", "on")

    @property
    def is_active(self) -> bool:
        """True when at least one agent actually deviates from the global LLM."""
        if not self.enabled:
            return False
        return any(self.spec_for(name).is_override for name in self.known_agents)

    @property
    def known_agents(self) -> list[str]:
        return sorted(str(k) for k in self._agents)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def tier_for(self, agent: str) -> str:
        """Return the tier name for an agent, defaulting to ``default_tier``."""
        tier = _clean(self._agents.get(agent))
        if tier and tier in self._tiers:
            return tier
        if tier:
            logger.warning(
                "Agent %r is mapped to unknown tier %r; using %r", agent, tier, self._default_tier
            )
        return self._default_tier

    def spec_for(self, agent: str) -> TierSpec:
        """Resolve the model/provider/temperature an agent should run with."""
        tier = self.tier_for(agent)
        if not self.enabled:
            return TierSpec(agent=agent, tier=tier)

        tier_cfg = self._tiers.get(tier)
        tier_cfg = tier_cfg if isinstance(tier_cfg, dict) else {}

        model = self._first(
            self._env.get(f"AGENT_MODEL_{agent.upper()}"),
            self._keys.get(f"agent_model_{agent.lower()}"),
            self._env.get(f"MODEL_TIER_{tier.upper()}"),
            self._keys.get(f"model_tier_{tier.lower()}"),
            tier_cfg.get("model"),
        )
        provider = self._first(
            self._env.get(f"AGENT_PROVIDER_{agent.upper()}"),
            self._keys.get(f"agent_provider_{agent.lower()}"),
            self._env.get(f"MODEL_TIER_{tier.upper()}_PROVIDER"),
            self._keys.get(f"model_tier_{tier.lower()}_provider"),
            tier_cfg.get("provider"),
        ).lower()

        if provider and provider not in VALID_PROVIDERS:
            logger.warning(
                "Ignoring unknown provider %r for agent %r (valid: %s)",
                provider, agent, ", ".join(VALID_PROVIDERS),
            )
            provider = ""

        return TierSpec(
            agent=agent,
            tier=tier,
            model=model,
            provider=provider,
            temperature=_coerce_temperature(tier_cfg.get("temperature")),
        )

    def describe(self) -> dict[str, dict[str, str]]:
        """Routing table for logs/diagnostics: only agents that deviate."""
        out: dict[str, dict[str, str]] = {}
        for name in self.known_agents:
            spec = self.spec_for(name)
            if spec.is_override:
                out[name] = {
                    "tier": spec.tier,
                    "model": spec.model or "<global>",
                    "provider": spec.provider or "<global>",
                }
        return out

    @staticmethod
    def _first(*candidates: Any) -> str:
        for candidate in candidates:
            value = _clean(candidate)
            if value:
                return value
        return ""


def _coerce_temperature(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning("Ignoring non-numeric temperature %r in model_routing.yaml", value)
        return None


def load_routing(
    keys: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    config: Mapping[str, Any] | None = None,
) -> Routing:
    """Convenience constructor mirroring how callers use it in production."""
    return Routing(config=config, env=env, keys=keys)
