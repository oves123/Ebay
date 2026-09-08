"""eBay Browse API client.

Handles client-credentials OAuth token fetch with in-memory cache and
automatic refresh on expiry. All methods are synchronous (run in a thread
from the async server via asyncio.to_thread).
"""

from __future__ import annotations

import base64
import time
from typing import Any

import requests

from ebay_mcp.config import EbayConfig, load_config

_DEFAULT_TIMEOUT = 15  # seconds


class EbayAPIError(Exception):
    """Raised when eBay returns a non-2xx response."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"eBay API error {status}: {body}")


class EbayBrowseClient:
    """Browse API client driven by EbayConfig."""

    def __init__(self, config: EbayConfig | None = None) -> None:
        self._cfg = config or load_config()
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    def _basic_auth_header(self) -> str:
        raw = f"{self._cfg.app_id}:{self._cfg.cert_id}"
        return "Basic " + base64.b64encode(raw.encode()).decode()

    def _fetch_token(self) -> None:
        from ebay_mcp.config import OAUTH_SCOPE

        resp = requests.post(
            self._cfg.token_url,
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": OAUTH_SCOPE,
            },
            timeout=_DEFAULT_TIMEOUT,
        )
        if not resp.ok:
            raise EbayAPIError(resp.status_code, resp.text)
        data = resp.json()
        self._access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 7200))
        self._token_expires_at = time.time() + expires_in - 60  # 60-sec buffer

    def _get_token(self) -> str:
        if self._access_token is None or time.time() >= self._token_expires_at:
            self._fetch_token()
        return self._access_token  # type: ignore[return-value]

    def _auth_headers(self, marketplace: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "X-EBAY-C-MARKETPLACE-ID": marketplace,
        }

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any], marketplace: str) -> dict[str, Any]:
        url = self._cfg.browse_base + path
        resp = requests.get(
            url,
            params=params,
            headers=self._auth_headers(marketplace),
            timeout=_DEFAULT_TIMEOUT,
        )
        if not resp.ok:
            raise EbayAPIError(resp.status_code, resp.text)
        return resp.json()  # type: ignore[no-any-return]

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        sort: str | None = None,
        filter: str | None = None,  # noqa: A002
        category_ids: str | None = None,
        marketplace: str = "EBAY_US",
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search for items via Browse API item_summary/search."""
        params: dict[str, Any] = {"q": query, "limit": limit, "offset": offset}
        if sort:
            params["sort"] = sort
        if filter:
            params["filter"] = filter
        if category_ids:
            params["category_ids"] = category_ids
        return self._get("/item_summary/search", params, marketplace)

    def get_item(
        self,
        item_id: str,
        *,
        marketplace: str = "EBAY_US",
    ) -> dict[str, Any]:
        """Fetch a single item by item ID via Browse API."""
        return self._get(f"/item/{item_id}", {}, marketplace)
