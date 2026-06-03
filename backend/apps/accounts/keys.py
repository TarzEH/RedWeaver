"""Adapter exposing a user's ApiKeyVault as the engine KeysProvider.

``redweaver_engine.llm_factory.LLMFactory`` and the tool registry consume an
object with ``get_all() -> dict``. The engine itself already merges process
env vars, so this only needs to surface the per-user vault values.
"""
from __future__ import annotations


class VaultKeysProvider:
    """KeysProvider backed by an ApiKeyVault row (or empty if none)."""

    def __init__(self, vault=None) -> None:
        self._vault = vault

    def get_all(self) -> dict:
        return self._vault.as_keys_dict() if self._vault is not None else {}


def keys_provider_for_user(user) -> VaultKeysProvider:
    from .models import ApiKeyVault

    vault = None
    if user is not None and getattr(user, "is_authenticated", False):
        vault = ApiKeyVault.objects.filter(user=user).first()
    return VaultKeysProvider(vault)
