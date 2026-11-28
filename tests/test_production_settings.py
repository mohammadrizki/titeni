import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def production_env(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.production",
        "DJANGO_DEBUG": "false",
        "DJANGO_SECRET_KEY": "abcdefghijklmnop" * 4,
        "DJANGO_ALLOWED_HOSTS": "titeni.example.test",
        "DATABASE_URL": "postgresql://titeni@127.0.0.1:5432/titeni_production_fixture",
        "DJANGO_STATIC_ROOT": str(tmp_path / "static"),
        "EVIDENCE_ARTIFACT_ROOT": str(tmp_path / "evidence"),
        "DJANGO_TRUST_HTTPS_PROXY": "false",
        "DJANGO_HSTS_SECONDS": "3600",
        "DJANGO_HSTS_INCLUDE_SUBDOMAINS": "false",
        "DJANGO_HSTS_PRELOAD": "false",
    }


def run_production(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "manage.py"), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize(
    ("key", "setting", "error"),
    [
        ("DJANGO_DEBUG", "true", "DJANGO_DEBUG must be false"),
        ("DJANGO_SECRET_KEY", "", "DJANGO_SECRET_KEY is required"),
        ("DJANGO_ALLOWED_HOSTS", "*", "Set DJANGO_ALLOWED_HOSTS"),
        ("DJANGO_HSTS_SECONDS", "-1", "DJANGO_HSTS_SECONDS cannot be negative"),
        ("DJANGO_STATIC_ROOT", "", "DJANGO_STATIC_ROOT must be an absolute path"),
        ("EVIDENCE_ARTIFACT_ROOT", "private", "EVIDENCE_ARTIFACT_ROOT must be an absolute path"),
    ],
)
def test_production_rejects_invalid_configuration(
    production_env: dict[str, str], key: str, setting: str, error: str
) -> None:
    result = run_production({**production_env, key: setting}, "check")
    assert result.returncode != 0
    assert error in result.stderr


def test_production_rejects_private_files_under_static_sources(
    production_env: dict[str, str],
) -> None:
    for public in (Path(production_env["DJANGO_STATIC_ROOT"]), ROOT / "static"):
        result = run_production(
            {**production_env, "EVIDENCE_ARTIFACT_ROOT": str(public / "evidence")}, "check"
        )
        assert result.returncode != 0
        assert "Private evidence and static directories must be disjoint." in result.stderr


@pytest.mark.parametrize("trusted_proxy", [False, True])
def test_production_applies_https_and_only_trusts_forwarding_when_configured(
    production_env: dict[str, str], trusted_proxy: bool
) -> None:
    script = """
from django.conf import settings
from django.test import Client

assert settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
client = Client(HTTP_HOST="titeni.example.test")
assert client.get("/").status_code == 301
direct = client.get("/", secure=True)
assert direct.status_code == 200
assert direct.headers["Strict-Transport-Security"] == "max-age=3600"
assert direct.headers["X-Content-Type-Options"] == "nosniff"
assert direct.headers["X-Frame-Options"] == "DENY"
assert client.get("/", secure=True, HTTP_HOST="outside.example.test").status_code == 400
forwarded = client.get("/", HTTP_X_FORWARDED_PROTO="https")
assert forwarded.status_code == (200 if settings.SECURE_PROXY_SSL_HEADER else 301)
"""
    result = run_production(
        {**production_env, "DJANGO_TRUST_HTTPS_PROXY": str(trusted_proxy).lower()},
        "shell",
        "-c",
        script,
    )
    assert result.returncode == 0, result.stderr
