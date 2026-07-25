"""The scope-guard contract the Ollama settings endpoints now depend on.

``/api/settings/ollama/health`` and ``/api/settings/ollama/models`` accept a
caller-supplied ``?url=`` and report back whether it answered (a liveness
oracle) plus any ``models`` JSON it returned. ``apps.accounts.settings_views``
runs that URL through ``check_target`` first; these tests pin the guard's
behaviour for the shapes that endpoint faces. (The view itself needs Django, so
it is not importable in this suite.)
"""
from redweaver_engine.tools.scope import check_target


def test_metadata_endpoint_is_refused():
    ok, reason = check_target("http://169.254.169.254/latest/meta-data")
    assert ok is False and "metadata" in reason.lower()


def test_link_local_is_refused():
    assert check_target("http://169.254.10.5:11434")[0] is False


def test_loopback_is_refused_by_default(monkeypatch):
    # "localhost" from the endpoint's point of view is the RedWeaver container
    # itself, not the caller's machine — so it is not the legitimate use case.
    monkeypatch.delenv("RW_ALLOW_LOOPBACK", raising=False)
    assert check_target("http://localhost:11434")[0] is False
    assert check_target("http://127.0.0.1:11434")[0] is False


def test_loopback_allowed_with_the_explicit_opt_in(monkeypatch):
    # Single-host deployments that really do run Ollama beside the worker.
    monkeypatch.setenv("RW_ALLOW_LOOPBACK", "1")
    assert check_target("http://127.0.0.1:11434")[0] is True


def test_a_users_own_ollama_host_still_passes(monkeypatch):
    # The legitimate case: a LAN/remote Ollama box. Private ranges are allowed
    # unless a locked-down deployment opts into blocking them.
    monkeypatch.delenv("RW_BLOCK_PRIVATE_TARGETS", raising=False)
    assert check_target("http://192.168.1.50:11434")[0] is True

    monkeypatch.setenv("RW_BLOCK_PRIVATE_TARGETS", "1")
    assert check_target("http://192.168.1.50:11434")[0] is False
