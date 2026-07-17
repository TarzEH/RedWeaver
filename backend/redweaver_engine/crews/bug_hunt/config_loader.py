"""Load and validate bug_hunt YAML configs (JSON-compatible YAML subset supported)."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)


def _parse_config_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    return json.loads(text)

_CONFIG_DIR = Path(__file__).resolve().parent / "config"


class CrewConfigError(RuntimeError):
    """Raised when agents.yaml or tasks.yaml is invalid."""


@lru_cache(maxsize=1)
def _load_raw_agents_file() -> dict[str, Any]:
    path = _CONFIG_DIR / "agents.yaml"
    if not path.is_file():
        raise CrewConfigError(f"Missing agents config: {path}")
    data = _parse_config_file(path)
    if not isinstance(data, dict) or "meta" not in data or "agents" not in data:
        raise CrewConfigError("agents.yaml must contain 'meta' and 'agents'")
    return data


@lru_cache(maxsize=1)
def _load_raw_tasks_file() -> dict[str, Any]:
    path = _CONFIG_DIR / "tasks.yaml"
    if not path.is_file():
        raise CrewConfigError(f"Missing tasks config: {path}")
    data = _parse_config_file(path)
    if not isinstance(data, dict) or "tasks" not in data:
        raise CrewConfigError("tasks.yaml must contain 'tasks'")
    return data


def get_display_names() -> dict[str, str]:
    meta = _load_raw_agents_file()["meta"]
    names = meta.get("display_names") or {}
    if not isinstance(names, dict):
        raise CrewConfigError("meta.display_names must be a mapping")
    return {str(k): str(v) for k, v in names.items()}


def get_agent_prompt_dicts() -> dict[str, dict[str, str]]:
    """Return role/goal/backstory for each agent, with finding-format suffix applied."""
    raw = _load_raw_agents_file()
    meta = raw["meta"]
    suffix = (meta.get("finding_format_instruction") or "").strip()
    suffix_agents = set(meta.get("agents_with_finding_suffix") or [])
    agents_raw = raw["agents"]
    out: dict[str, dict[str, str]] = {}
    for name, cfg in agents_raw.items():
        if not isinstance(cfg, dict):
            raise CrewConfigError(f"agents.{name} must be a mapping")
        for key in ("role", "goal", "backstory"):
            if key not in cfg:
                raise CrewConfigError(f"agents.{name} missing '{key}'")
        bs = str(cfg["backstory"])
        if name in suffix_agents and suffix:
            bs = bs.rstrip() + "\n\n" + suffix
        out[str(name)] = {
            "role": str(cfg["role"]),
            "goal": str(cfg["goal"]),
            "backstory": bs,
        }
    return out


def get_task_description_templates() -> dict[str, str]:
    raw = _load_raw_tasks_file()
    tasks = raw["tasks"]
    if not isinstance(tasks, dict):
        raise CrewConfigError("tasks must be a mapping of task_key -> template string")
    return {str(k): str(v) for k, v in tasks.items()}


def validate_configs() -> None:
    """Ensure every task template key has a matching agent where needed (light check)."""
    agents = get_agent_prompt_dicts()
    tasks = get_task_description_templates()
    agent_keys = set(agents.keys())
    task_keys = set(tasks.keys())
    missing_tasks = agent_keys - task_keys - {"orchestrator"}
    if missing_tasks:
        logger.warning("Agents without task templates (may be intentional): %s", missing_tasks)
    unknown_in_tasks = task_keys - agent_keys - {
        "recon", "crawler", "vuln_scanner", "fuzzer", "web_search",
        "exploit_analyst", "report_writer", "privesc", "tunnel_pivot", "post_exploit",
    }
    if unknown_in_tasks:
        logger.warning("Task keys not in agent definitions: %s", unknown_in_tasks)
