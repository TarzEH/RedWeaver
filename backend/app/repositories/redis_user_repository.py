"""Redis-backed user storage."""

from __future__ import annotations

import logging
from typing import Any

import redis

from app.domain.user import User

logger = logging.getLogger(__name__)

KEY_PREFIX = "user:"
INDEX_KEY = "users:all"
EMAIL_INDEX = "users:email:"
USERNAME_INDEX = "users:username:"


class RedisUserRepository:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def create(self, user: User) -> None:
        pipe = self._r.pipeline()
        pipe.set(f"{KEY_PREFIX}{user.id}", user.model_dump_json())
        pipe.sadd(INDEX_KEY, user.id)
        pipe.set(f"{EMAIL_INDEX}{user.email.lower()}", user.id)
        pipe.set(f"{USERNAME_INDEX}{user.username.lower()}", user.id)
        pipe.execute()

    def get(self, user_id: str) -> User | None:
        raw = self._r.get(f"{KEY_PREFIX}{user_id}")
        return User.model_validate_json(raw) if raw else None

    def get_by_email(self, email: str) -> User | None:
        user_id = self._r.get(f"{EMAIL_INDEX}{email.lower()}")
        if not user_id:
            return None
        return self.get(user_id)

    def get_by_username(self, username: str) -> User | None:
        user_id = self._r.get(f"{USERNAME_INDEX}{username.lower()}")
        if not user_id:
            return None
        return self.get(user_id)

    def update(self, user_id: str, updates: dict[str, Any]) -> None:
        user = self.get(user_id)
        if not user:
            return
        data = user.model_dump()
        data.update(updates)
        updated = User.model_validate(data)
        self._r.set(f"{KEY_PREFIX}{user_id}", updated.model_dump_json())

    def delete(self, user_id: str) -> bool:
        user = self.get(user_id)
        if not user:
            return False
        pipe = self._r.pipeline()
        pipe.delete(f"{KEY_PREFIX}{user_id}")
        pipe.srem(INDEX_KEY, user_id)
        pipe.delete(f"{EMAIL_INDEX}{user.email.lower()}")
        pipe.delete(f"{USERNAME_INDEX}{user.username.lower()}")
        pipe.execute()
        return True
