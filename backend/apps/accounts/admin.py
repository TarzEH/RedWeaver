"""Admin for accounts: custom User + masked ApiKeyVault."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import ApiKeyVault, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-created_at"]
    list_display = ("email", "username", "role", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "username")
    readonly_fields = ("id", "created_at", "updated_at", "last_login")
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Role & status", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Meta", {"fields": ("id", "created_at", "updated_at", "last_login")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2",
                           "role", "is_staff", "is_superuser"),
            },
        ),
    )


@admin.register(ApiKeyVault)
class ApiKeyVaultAdmin(admin.ModelAdmin):
    list_display = (
        "user", "model_provider", "selected_model",
        "openai_set", "anthropic_set", "google_set", "ollama_base_url",
    )
    search_fields = ("user__email",)
    readonly_fields = ("id", "created_at", "updated_at")

    @admin.display(boolean=True, description="OpenAI")
    def openai_set(self, obj) -> bool:
        return bool(obj.openai_api_key)

    @admin.display(boolean=True, description="Anthropic")
    def anthropic_set(self, obj) -> bool:
        return bool(obj.anthropic_api_key)

    @admin.display(boolean=True, description="Google")
    def google_set(self, obj) -> bool:
        return bool(obj.google_api_key)
