"""Local development settings."""

from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]

# Emails are printed to the console in development.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
