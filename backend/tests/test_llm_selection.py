"""Unit tests for provider/model resolution feeding the CrewAI LLM.

The regression these exist to prevent: routing must not quietly override the
model a user picked in Settings. With no routing override the resolution has to
return exactly what it returned before routing existed.
"""
import pytest

from apps.hunts.crew_factory import resolve_model_selection
from redweaver_engine.llm_factory import LLMFactory

# Provider resolution falls back to the environment, so a developer's or CI
# runner's real keys would leak into these assertions. Clear them for every test.
_PROVIDER_ENV = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
    "OLLAMA_BASE_URL", "MODEL_PROVIDER",
)


@pytest.fixture(autouse=True)
def _clean_provider_env(monkeypatch):
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)


class FakeKeys:
    def __init__(self, **keys):
        self._keys = keys

    def get_all(self):
        return dict(self._keys)


def factory(**keys):
    return LLMFactory(FakeKeys(**keys))


def selection(keys=None, provider="", model="", **factory_keys):
    lf = factory(**factory_keys)
    return resolve_model_selection(lf, keys if keys is not None else factory_keys, provider, model)


# ── no routing override: pre-routing behaviour, exactly ────────────────────
def test_user_selected_model_is_honoured_when_nothing_is_routed():
    keys = {"openai_api_key": "sk-test", "selected_model": "gpt-4.1"}
    assert selection(**keys) == ("openai", "gpt-4.1")


def test_provider_default_is_used_when_no_model_is_selected():
    keys = {"openai_api_key": "sk-test"}
    provider, model = selection(**keys)
    assert provider == "openai"
    assert model == LLMFactory.DEFAULT_MODELS["openai"]


def test_provider_is_auto_detected_from_the_available_key():
    assert selection(anthropic_api_key="sk-ant")[0] == "anthropic"


# ── routing overrides ──────────────────────────────────────────────────────
def test_routed_model_wins_over_the_selected_model():
    keys = {"openai_api_key": "sk-test", "selected_model": "gpt-4.1"}
    assert selection(model="gpt-4.1-nano", **keys) == ("openai", "gpt-4.1-nano")


def test_routed_provider_without_a_model_uses_that_providers_default():
    # The selected OpenAI model does not exist on Anthropic, so it must not
    # be carried across.
    keys = {"openai_api_key": "sk-test", "selected_model": "gpt-4.1"}
    provider, model = selection(provider="anthropic", **keys)
    assert provider == "anthropic"
    assert model == LLMFactory.DEFAULT_MODELS["anthropic"]
    assert model != "gpt-4.1"


def test_routed_provider_and_model_are_both_respected():
    keys = {"openai_api_key": "sk-test", "selected_model": "gpt-4.1"}
    assert selection(provider="ollama", model="llama3.2", **keys) == ("ollama", "llama3.2")


def test_routed_model_without_a_provider_keeps_the_global_provider():
    keys = {"anthropic_api_key": "sk-ant", "selected_model": "claude-sonnet-4-6"}
    assert selection(model="claude-haiku-4-5", **keys) == ("anthropic", "claude-haiku-4-5")


def test_ollama_is_never_selected_without_configuration():
    # No keys at all: the factory falls back to openai, not to a local runtime.
    assert selection()[0] == "openai"
    # An Ollama URL alone is a deliberate configuration, so it may be selected.
    assert selection(ollama_base_url="http://localhost:11434")[0] == "ollama"
