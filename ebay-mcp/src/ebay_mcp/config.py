"""Configuration loader for ebay-mcp.

Load order (highest to lowest priority):
  1. Environment variables: EBAY_ENV, EBAY_PRD_APP_ID, EBAY_PRD_CERT_ID,
     EBAY_SBX_APP_ID, EBAY_SBX_CERT_ID, EBAY_DEV_ID
  2. ~/.ebay-mcp.toml

The active ``env`` selects both the keyset AND base URLs together so they
can never mismatch.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_TOML_PATH = Path.home() / ".ebay-mcp.toml"

_PROD_API_BASE = "https://api.ebay.com"
_SBX_API_BASE = "https://api.sandbox.ebay.com"

OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"


@dataclass
class EbayConfig:
    env: str  # "production" or "sandbox"
    app_id: str
    cert_id: str
    dev_id: str | None
    api_base: str
    token_url: str

    @property
    def browse_base(self) -> str:
        return f"{self.api_base}/buy/browse/v1"


def load_config() -> EbayConfig:
    """Return an EbayConfig, merging env vars over the TOML file."""
    # Load .env file if it exists in current directory
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with env_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k not in os.environ:
                        os.environ[k.strip()] = v.strip()

    # Read TOML if it exists
    toml_data: dict[str, Any] = {}
    if _TOML_PATH.exists():
        with _TOML_PATH.open("rb") as f:
            toml_data = tomllib.load(f)

    # Determine active environment
    env = (
        os.environ.get("EBAY_ENV")
        or toml_data.get("env")
        or "production"
    ).lower()

    if env not in ("production", "sandbox"):
        raise ValueError(f"EBAY_ENV must be 'production' or 'sandbox', got {env!r}")

    # Pull keyset — env vars win over TOML
    if env == "production":
        section = toml_data.get("production", {})
        app_id = os.environ.get("EBAY_PRD_APP_ID") or section.get("app_id", "")
        cert_id = os.environ.get("EBAY_PRD_CERT_ID") or section.get("cert_id", "")
        api_base = _PROD_API_BASE
    else:
        section = toml_data.get("sandbox", {})
        app_id = os.environ.get("EBAY_SBX_APP_ID") or section.get("app_id", "")
        cert_id = os.environ.get("EBAY_SBX_CERT_ID") or section.get("cert_id", "")
        api_base = _SBX_API_BASE

    dev_id = os.environ.get("EBAY_DEV_ID") or toml_data.get("dev_id") or section.get("dev_id")

    if not app_id:
        raise ValueError(
            f"Missing app_id for env={env!r}. Set EBAY_{'PRD' if env == 'production' else 'SBX'}"
            "_APP_ID or add it to ~/.ebay-mcp.toml."
        )
    if not cert_id:
        raise ValueError(
            f"Missing cert_id for env={env!r}. Set EBAY_{'PRD' if env == 'production' else 'SBX'}"
            "_CERT_ID or add it to ~/.ebay-mcp.toml."
        )

    token_url = f"{api_base}/identity/v1/oauth2/token"

    return EbayConfig(
        env=env,
        app_id=app_id,
        cert_id=cert_id,
        dev_id=dev_id,
        api_base=api_base,
        token_url=token_url,
    )


def main() -> None:
    """Print active config with masked credentials."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="ebay-mcp-config",
        description="Validate and display active ebay-mcp configuration.",
    )
    parser.parse_args()

    try:
        cfg = load_config()
    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    def mask(s: str) -> str:
        if len(s) <= 8:
            return "****"
        return s[:4] + "****" + s[-4:]

    toml_note = f"  (from {_TOML_PATH})" if _TOML_PATH.exists() else "  (no ~/.ebay-mcp.toml found)"
    print(f"env:      {cfg.env}")
    print(f"app_id:   {mask(cfg.app_id)}")
    print(f"cert_id:  {mask(cfg.cert_id)}")
    print(f"dev_id:   {mask(cfg.dev_id) if cfg.dev_id else '(not set)'}")
    print(f"api_base: {cfg.api_base}")
    print(f"config:   {toml_note.strip()}")
    print("OK — configuration is valid.")
