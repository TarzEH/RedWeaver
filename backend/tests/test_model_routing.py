"""Unit tests for per-agent model routing.

The contract that matters most: an unconfigured install must resolve to nothing,
so every agent keeps using the globally selected model and no provider — least
of all a local one — is ever picked implicitly.
"""
from redweaver_engine.model_routing import Routing, load_config_file

CONFIG = {
    "tiers": {
        "fast": {"model": "", "provider": "", "temperature": 0.1},
        "standard": {"model": "", "provider": "", "temperature": 0.1},
        "deep": {"model": "", "provider": "", "temperature": 0.2},
    },
    "default_tier": "standard",
    "agents": {"recon": "fast", "exploit_analyst": "deep", "vuln_scanner": "standard"},
}


def routing(env=None, keys=None, config=None):
    return Routing(config=config or CONFIG, env=env or {}, keys=keys or {})


# ── inactive by default ────────────────────────────────────────────────────
def test_unconfigured_routing_overrides_nothing():
    r = routing()
    assert r.is_active is False
    for agent in ("recon", "exploit_analyst", "vuln_scanner"):
        spec = r.spec_for(agent)
        assert spec.model == ""
        assert spec.provider == ""
        assert spec.is_override is False


def test_shipped_config_file_is_inert():
    # The committed model_routing.yaml must not silently route anyone anywhere.
    r = Routing(config=load_config_file(), env={}, keys={})
    assert r.is_active is False, f"shipped config routes agents: {r.describe()}"


def test_no_provider_is_ever_inferred():
    # Naming a model must not drag a provider along with it.
    r = routing(env={"MODEL_TIER_FAST": "some-local-model"})
    assert r.spec_for("recon").provider == ""


# ── tier assignment ────────────────────────────────────────────────────────
def test_agents_map_to_their_declared_tier():
    r = routing()
    assert r.tier_for("recon") == "fast"
    assert r.tier_for("exploit_analyst") == "deep"


def test_unknown_agent_falls_back_to_default_tier():
    assert routing().tier_for("agent-that-does-not-exist") == "standard"


def test_agent_mapped_to_unknown_tier_falls_back():
    config = {**CONFIG, "agents": {"recon": "nonexistent-tier"}}
    assert routing(config=config).tier_for("recon") == "standard"


# ── resolution precedence ──────────────────────────────────────────────────
def test_tier_env_var_routes_every_agent_on_that_tier():
    r = routing(env={"MODEL_TIER_FAST": "gpt-4.1-nano"})
    assert r.spec_for("recon").model == "gpt-4.1-nano"
    assert r.spec_for("exploit_analyst").model == ""  # different tier, untouched
    assert r.is_active is True


def test_per_agent_env_beats_tier_env():
    r = routing(env={"MODEL_TIER_FAST": "tier-model", "AGENT_MODEL_RECON": "agent-model"})
    assert r.spec_for("recon").model == "agent-model"


def test_env_beats_vault_keys_which_beat_the_config_file():
    config = {**CONFIG, "tiers": {**CONFIG["tiers"], "fast": {"model": "file-model"}}}

    assert routing(config=config).spec_for("recon").model == "file-model"

    from_keys = routing(config=config, keys={"model_tier_fast": "keys-model"})
    assert from_keys.spec_for("recon").model == "keys-model"

    from_env = routing(
        config=config,
        env={"MODEL_TIER_FAST": "env-model"},
        keys={"model_tier_fast": "keys-model"},
    )
    assert from_env.spec_for("recon").model == "env-model"


def test_temperature_comes_from_the_tier():
    r = routing(env={"MODEL_TIER_DEEP": "big-model"})
    assert r.spec_for("exploit_analyst").temperature == 0.2


# ── local providers are opt-in only ────────────────────────────────────────
def test_ollama_is_used_only_when_named_explicitly():
    r = routing(env={"MODEL_TIER_FAST_PROVIDER": "ollama", "MODEL_TIER_FAST": "llama3.2"})
    spec = r.spec_for("recon")
    assert spec.provider == "ollama"
    assert spec.is_override is True
    # ...and only for that tier.
    assert routing().spec_for("recon").provider == ""


def test_unknown_provider_is_rejected_not_passed_through():
    r = routing(env={"AGENT_PROVIDER_RECON": "definitely-not-a-provider"})
    assert r.spec_for("recon").provider == ""


def test_provider_only_override_still_counts_as_an_override():
    # "run this tier on Anthropic, default model" is a legitimate config.
    spec = routing(env={"MODEL_TIER_FAST_PROVIDER": "anthropic"}).spec_for("recon")
    assert spec.provider == "anthropic"
    assert spec.model == ""
    assert spec.is_override is True


# ── kill switch ────────────────────────────────────────────────────────────
def test_kill_switch_disables_all_overrides():
    env = {"MODEL_TIER_FAST": "gpt-4.1-nano", "MODEL_ROUTING_ENABLED": "false"}
    r = routing(env=env)
    assert r.enabled is False
    assert r.is_active is False
    assert r.spec_for("recon").is_override is False


def test_kill_switch_absent_means_enabled():
    assert routing().enabled is True


# ── diagnostics ────────────────────────────────────────────────────────────
def test_describe_lists_only_deviating_agents():
    r = routing(env={"MODEL_TIER_FAST": "gpt-4.1-nano"})
    described = r.describe()
    assert set(described) == {"recon"}
    assert described["recon"]["model"] == "gpt-4.1-nano"
    assert described["recon"]["provider"] == "<global>"
