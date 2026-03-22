"""Redis-backed finding storage implementing FindingRepositoryProtocol."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

from app.domain.finding import Finding, FindingStatus

logger = logging.getLogger(__name__)

KEY_PREFIX = "finding:"
HUNT_INDEX = "findings:hunt:"
SESSION_INDEX = "findings:session:"
ALL_INDEX = "findings:all"


class RedisFindingRepository:
    """Finding store backed by Redis."""

    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def create(self, finding: Finding) -> None:
        pipe = self._r.pipeline()
        pipe.set(f"{KEY_PREFIX}{finding.id}", finding.model_dump_json())
        pipe.sadd(ALL_INDEX, finding.id)
        if finding.hunt_id:
            pipe.sadd(f"{HUNT_INDEX}{finding.hunt_id}", finding.id)
        if finding.session_id:
            pipe.sadd(f"{SESSION_INDEX}{finding.session_id}", finding.id)
        pipe.execute()

    def get(self, finding_id: str) -> Finding | None:
        raw = self._r.get(f"{KEY_PREFIX}{finding_id}")
        if raw is None:
            return None
        return Finding.model_validate_json(raw)

    def list_for_hunt(self, hunt_id: str) -> list[Finding]:
        ids = self._r.smembers(f"{HUNT_INDEX}{hunt_id}")
        return self._get_many(ids)

    def list_for_session(self, session_id: str) -> list[Finding]:
        ids = self._r.smembers(f"{SESSION_INDEX}{session_id}")
        return self._get_many(ids)

    def list_filtered(
        self,
        session_id: str | None = None,
        hunt_id: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        agent_source: str | None = None,
        search: str | None = None,
    ) -> list[Finding]:
        # Get base set
        if hunt_id:
            ids = self._r.smembers(f"{HUNT_INDEX}{hunt_id}")
        elif session_id:
            ids = self._r.smembers(f"{SESSION_INDEX}{session_id}")
        else:
            ids = self._r.smembers(ALL_INDEX)

        findings = self._get_many(ids)

        # Apply filters
        if severity:
            findings = [f for f in findings if f.severity.value == severity]
        if status:
            findings = [f for f in findings if f.status.value == status]
        if agent_source:
            findings = [f for f in findings if f.agent_source == agent_source]
        if search:
            q = search.lower()
            findings = [f for f in findings if q in f.title.lower() or q in f.description.lower()]

        return sorted(findings, key=lambda f: f.created_at, reverse=True)

    def update_status(self, finding_id: str, status: FindingStatus) -> None:
        finding = self.get(finding_id)
        if finding:
            finding.status = status
            self._r.set(f"{KEY_PREFIX}{finding_id}", finding.model_dump_json())

    def delete(self, finding_id: str) -> bool:
        finding = self.get(finding_id)
        if not finding:
            return False
        pipe = self._r.pipeline()
        pipe.delete(f"{KEY_PREFIX}{finding_id}")
        pipe.srem(ALL_INDEX, finding_id)
        if finding.hunt_id:
            pipe.srem(f"{HUNT_INDEX}{finding.hunt_id}", finding_id)
        if finding.session_id:
            pipe.srem(f"{SESSION_INDEX}{finding.session_id}", finding_id)
        pipe.execute()
        return True

    def count_for_hunt(self, hunt_id: str) -> int:
        return self._r.scard(f"{HUNT_INDEX}{hunt_id}") or 0

    def count_for_session(self, session_id: str) -> int:
        return self._r.scard(f"{SESSION_INDEX}{session_id}") or 0

    def _get_many(self, ids: set) -> list[Finding]:
        if not ids:
            return []
        keys = [f"{KEY_PREFIX}{fid}" for fid in ids]
        values = self._r.mget(keys)
        results: list[Finding] = []
        for val in values:
            if val is not None:
                try:
                    results.append(Finding.model_validate_json(val))
                except Exception:
                    logger.exception("Failed to deserialize finding")
        return results
