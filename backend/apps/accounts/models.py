"""Accounts: custom User (email login, role) + encrypted API key vault."""
import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.common.fields import EncryptedTextField
from apps.common.models import TimeStampedUUIDModel


class UserRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    OPERATOR = "operator", "Operator"
    VIEWER = "viewer", "Viewer"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        extra.setdefault("role", UserRole.OPERATOR)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", UserRole.ADMIN)
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Email-as-username principal with a coarse role.

    Replaces legacy ``domain.user.User`` (email/username/role/is_active +
    workspace_ids). Workspace membership now lives on Workspace.members
    (reverse accessor ``user.workspaces``).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=150, blank=True)
    role = models.CharField(
        max_length=16, choices=UserRole.choices, default=UserRole.OPERATOR
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email


class ApiKeyVault(TimeStampedUUIDModel):
    """Per-user LLM/provider credentials (secrets encrypted at rest).

    Replaces data/api_keys.json + redis_api_keys_repository. ``as_keys_dict``
    produces the flat dict that ``redweaver_engine.llm_factory.LLMFactory`` and
    the tool registry consume (the KeysProvider protocol).
    """

    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="api_keys"
    )
    openai_api_key = EncryptedTextField(blank=True, default="")
    anthropic_api_key = EncryptedTextField(blank=True, default="")
    google_api_key = EncryptedTextField(blank=True, default="")
    virustotal_api_key = EncryptedTextField(blank=True, default="")
    urlscan_api_key = EncryptedTextField(blank=True, default="")
    ollama_base_url = models.CharField(max_length=255, blank=True, default="")
    model_provider = models.CharField(max_length=32, blank=True, default="")
    selected_model = models.CharField(max_length=128, blank=True, default="")

    def __str__(self) -> str:
        return f"ApiKeyVault<{self.user_id}>"

    def as_keys_dict(self) -> dict[str, str]:
        """Flat key dict consumed by the engine (KeysProvider.get_all())."""
        return {
            "openai_api_key": self.openai_api_key or "",
            "anthropic_api_key": self.anthropic_api_key or "",
            "google_api_key": self.google_api_key or "",
            "virustotal_api_key": self.virustotal_api_key or "",
            "urlscan_api_key": self.urlscan_api_key or "",
            "ollama_base_url": self.ollama_base_url or "",
            "model_provider": self.model_provider or "",
            "selected_model": self.selected_model or "",
        }
