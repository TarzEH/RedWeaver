"""Custom model fields — symmetric encryption for secrets at rest."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet() -> Fernet:
    """Derive a stable Fernet key from FIELD_ENCRYPTION_KEY (or SECRET_KEY).

    Any string works as the configured key: we SHA-256 it to 32 bytes and
    urlsafe-b64encode to the Fernet key format.
    """
    raw = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class EncryptedTextField(models.TextField):
    """TextField that transparently encrypts on write and decrypts on read.

    Tolerates legacy/plaintext values (returns them as-is if not decryptable)
    so the column can be migrated without a data step.
    """

    def get_prep_value(self, value):
        if value in (None, ""):
            return value
        token = _fernet().encrypt(str(value).encode("utf-8"))
        return token.decode("utf-8")

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        try:
            return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError, TypeError):
            return value
