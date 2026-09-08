# ebay-mcp

eBay Browse API MCP server — read-only, buy-side listing search and price intelligence.

## Package layout

```
src/ebay_mcp/
  __init__.py   version
  config.py     credential loader (TOML + env vars) + ebay-mcp-config CLI
  browse.py     EbayBrowseClient — OAuth token cache + Browse API calls
  server.py     MCP server (list_tools / call_tool / main)
tests/
  test_config.py   config load + env-var precedence (no network)
  test_server.py   dispatch + price aggregation (mocked client)
```

## Credentials

Stored in `~/.ebay-mcp.toml` (chmod 600). Never committed. Env vars override TOML.
Uses eBay's application client-credentials grant — no user login, no stored user data.
This server only reads public buy-side listing data and does not persist any eBay data.

## Dev

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
mypy src/
pytest
ebay-mcp-config      # validate active credentials
```

## Tools

| Tool | What it does |
|------|-------------|
| `ebay_search` | Listing search with sort/filter/category |
| `ebay_get_item` | Single item detail by ID |
| `ebay_price_check` | Aggregated price landscape (min/median/max by condition) |
