"""Idempotently create a default admin from DJANGO_SUPERUSER_* env vars."""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a default superuser if one does not already exist."

    def handle(self, *args, **options):
        User = get_user_model()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@redweaver.local")
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin")

        if User.objects.filter(email=email).exists():
            self.stdout.write(f"Admin {email} already exists; skipping.")
            return
        User.objects.create_superuser(
            email=email, password=password, username=username
        )
        self.stdout.write(self.style.SUCCESS(f"Created admin {email}"))
