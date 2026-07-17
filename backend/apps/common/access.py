"""Per-user / per-workspace authorization scoping.

Closes the IDOR where every viewset exposed ``.objects.all()`` to any
authenticated user. A user may access an object if they created it or belong
to its workspace (owner or member). Superusers bypass all scoping.
"""
from __future__ import annotations

from django.db.models import Q
from django.http import Http404


# --- ownership predicates (Q objects) keyed off each model's relations ---------

def run_scope_q(user) -> Q:
    return (
        Q(created_by=user)
        | Q(workspace__owner=user)
        | Q(workspace__members=user)
        | Q(session__created_by=user)
    )


def session_scope_q(user) -> Q:
    return (
        Q(created_by=user)
        | Q(workspace__owner=user)
        | Q(workspace__members=user)
    )


def target_scope_q(user) -> Q:
    return (
        Q(session__created_by=user)
        | Q(session__workspace__owner=user)
        | Q(session__workspace__members=user)
    )


def finding_scope_q(user) -> Q:
    return (
        Q(run__created_by=user)
        | Q(run__workspace__owner=user)
        | Q(run__workspace__members=user)
        | Q(run__session__created_by=user)
    )


class ScopedQuerysetMixin:
    """Restrict a viewset's queryset to objects the user may access.

    Set ``scope_q`` to a callable ``(user) -> Q``. Superusers see everything.
    Place this FIRST in the bases so subclass ``get_queryset`` overrides that
    call ``super().get_queryset()`` still get scoped.
    """

    scope_q = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if user is None or getattr(user, "is_superuser", False):
            return qs
        if self.scope_q is None:
            return qs
        return qs.filter(self.scope_q(user)).distinct()


def scoped_get_or_404(model, user, scope_fn, **lookup):
    """Fetch one object enforcing access scope (404 if missing or not owned)."""
    qs = model.objects.all()
    if not getattr(user, "is_superuser", False):
        qs = qs.filter(scope_fn(user))
    obj = qs.filter(**lookup).first()
    if obj is None:
        raise Http404("Not found")
    return obj
