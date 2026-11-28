"""Production settings selected explicitly by the deployment environment."""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from . import settings as base
from .settings import *  # noqa: F403

if base.DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be false with config.production.")

if not base.SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required with config.production.")

ALLOWED_HOSTS = base.env.list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS or any(host == "*" for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS to the deployment hostnames.")

# Require a deployment database URL instead of using the development fallback.
base.env.str("DATABASE_URL")


def configured_directory(name: str) -> Path:
    path = Path(base.env.str(name))
    if not path.is_absolute():
        raise ImproperlyConfigured(f"{name} must be an absolute path.")
    return path.resolve()


STATIC_ROOT = configured_directory("DJANGO_STATIC_ROOT")
EVIDENCE_ARTIFACT_ROOT = configured_directory("EVIDENCE_ARTIFACT_ROOT")
for directory in (STATIC_ROOT, *base.STATICFILES_DIRS):
    public_path = Path(directory).resolve()
    if EVIDENCE_ARTIFACT_ROOT.is_relative_to(public_path) or public_path.is_relative_to(
        EVIDENCE_ARTIFACT_ROOT
    ):
        raise ImproperlyConfigured("Private evidence and static directories must be disjoint.")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = base.env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

SECURE_HSTS_SECONDS = base.env.int("DJANGO_HSTS_SECONDS", default=3600)
if SECURE_HSTS_SECONDS < 0:
    raise ImproperlyConfigured("DJANGO_HSTS_SECONDS cannot be negative.")
SECURE_HSTS_INCLUDE_SUBDOMAINS = base.env.bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = base.env.bool("DJANGO_HSTS_PRELOAD", default=False)

SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if base.env.bool("DJANGO_TRUST_HTTPS_PROXY", default=False)
    else None
)
