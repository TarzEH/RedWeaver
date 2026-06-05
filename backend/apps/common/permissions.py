"""Role-based write protection.

The User model has a role enum (admin / operator / viewer) that was defined but
never enforced. This permission makes ``viewer`` accounts read-only on the
sensitive mutating endpoints (runs, sessions, targets, findings) while leaving
reads open to everyone authenticated. admin/operator (and superusers) keep full
access.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission


class RoleWritePermission(BasePermission):
    message = "Your role is read-only (viewer)."

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, "is_superuser", False):
            return True
        # Only an explicit "viewer" is blocked from writes.
        return getattr(user, "role", None) != "viewer"
