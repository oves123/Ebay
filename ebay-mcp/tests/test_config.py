"""Tests for config loading — env-var precedence and TOML fallback."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import ebay_mcp.config as config_mod
from ebay_mcp.config import load_config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Strip all EBAY_* env vars so tests start from a clean slate."""
    for key in list(os.environ):
        if key.startswith("EBAY_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def tmp_toml(tmp_path, monkeypatch):
    """Point _TOML_PATH at a temp file and return the path."""
    toml_path = tmp_path / ".ebay-mcp.toml"
    monkeypatch.setattr(config_mod, "_TOML_PATH", toml_path)
    return toml_path


def write_toml(path: Path, content: str) -> None:
    path.write_text(content)


# ---------------------------------------------------------------------------
# Load from TOML
# ---------------------------------------------------------------------------

def test_loads_production_from_toml(tmp_toml):
    write_toml(tmp_toml, """
env = "production"
[production]
app_id = "TOML_PRD_APP"
cert_id = "TOML_PRD_CERT"
""")
    cfg = load_config()
    assert cfg.env == "production"
    assert cfg.app_id == "TOML_PRD_APP"
    assert cfg.cert_id == "TOML_PRD_CERT"
    assert "api.ebay.com" in cfg.api_base
    assert "sandbox" not in cfg.api_base


def test_loads_sandbox_from_toml(tmp_toml):
    write_toml(tmp_toml, """
env = "sandbox"
[sandbox]
app_id = "TOML_SBX_APP"
cert_id = "TOML_SBX_CERT"
""")
    cfg = load_config()
    assert cfg.env == "sandbox"
    assert cfg.app_id == "TOML_SBX_APP"
    assert "sandbox.ebay.com" in cfg.api_base


# ---------------------------------------------------------------------------
# Env var precedence
# ---------------------------------------------------------------------------

def test_env_var_overrides_toml_app_id(tmp_toml, monkeypatch):
    write_toml(tmp_toml, """
env = "production"
[production]
app_id = "TOML_PRD_APP"
cert_id = "TOML_PRD_CERT"
""")
    monkeypatch.setenv("EBAY_PRD_APP_ID", "ENV_PRD_APP")
    cfg = load_config()
    assert cfg.app_id == "ENV_PRD_APP"
    assert cfg.cert_id == "TOML_PRD_CERT"


def test_env_overrides_env_selection(tmp_toml, monkeypatch):
    write_toml(tmp_toml, """
env = "production"
[production]
app_id = "TOML_PRD_APP"
cert_id = "TOML_PRD_CERT"
[sandbox]
app_id = "TOML_SBX_APP"
cert_id = "TOML_SBX_CERT"
""")
    monkeypatch.setenv("EBAY_ENV", "sandbox")
    cfg = load_config()
    assert cfg.env == "sandbox"
    assert cfg.app_id == "TOML_SBX_APP"


def test_env_vars_only_no_toml(tmp_toml, monkeypatch):
    # tmp_toml doesn't exist yet, no write
    monkeypatch.setenv("EBAY_ENV", "production")
    monkeypatch.setenv("EBAY_PRD_APP_ID", "ENV_APP")
    monkeypatch.setenv("EBAY_PRD_CERT_ID", "ENV_CERT")
    cfg = load_config()
    assert cfg.app_id == "ENV_APP"
    assert cfg.cert_id == "ENV_CERT"


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------

def test_missing_app_id_raises(tmp_toml, monkeypatch):
    write_toml(tmp_toml, """
env = "production"
[production]
cert_id = "SOME_CERT"
""")
    with pytest.raises(ValueError, match="Missing app_id"):
        load_config()


def test_missing_cert_id_raises(tmp_toml, monkeypatch):
    write_toml(tmp_toml, """
env = "production"
[production]
app_id = "SOME_APP"
""")
    with pytest.raises(ValueError, match="Missing cert_id"):
        load_config()


def test_invalid_env_raises(tmp_toml, monkeypatch):
    monkeypatch.setenv("EBAY_ENV", "staging")
    monkeypatch.setenv("EBAY_PRD_APP_ID", "x")
    monkeypatch.setenv("EBAY_PRD_CERT_ID", "y")
    with pytest.raises(ValueError, match="must be 'production' or 'sandbox'"):
        load_config()


# ---------------------------------------------------------------------------
# URL consistency
# ---------------------------------------------------------------------------

def test_prod_urls_never_contain_sandbox(tmp_toml, monkeypatch):
    monkeypatch.setenv("EBAY_ENV", "production")
    monkeypatch.setenv("EBAY_PRD_APP_ID", "A")
    monkeypatch.setenv("EBAY_PRD_CERT_ID", "B")
    cfg = load_config()
    assert "sandbox" not in cfg.api_base
    assert "sandbox" not in cfg.token_url
    assert "sandbox" not in cfg.browse_base


def test_sandbox_urls_always_contain_sandbox(tmp_toml, monkeypatch):
    monkeypatch.setenv("EBAY_ENV", "sandbox")
    monkeypatch.setenv("EBAY_SBX_APP_ID", "A")
    monkeypatch.setenv("EBAY_SBX_CERT_ID", "B")
    cfg = load_config()
    assert "sandbox" in cfg.api_base
    assert "sandbox" in cfg.token_url
