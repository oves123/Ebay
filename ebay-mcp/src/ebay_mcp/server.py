"""eBay MCP server — buy-side Browse API tools over stdio.

Three read-only tools:
  ebay_search       — full listing search with filtering/sorting
  ebay_get_item     — fetch a single item by ID
  ebay_price_check  — search + aggregate price landscape by condition
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ebay_mcp.browse import EbayAPIError, EbayBrowseClient
from ebay_mcp.config import load_config

logger = logging.getLogger(__name__)

app = Server("ebay-mcp")

_client: EbayBrowseClient | None = None


def get_client() -> EbayBrowseClient:
    global _client
    if _client is None:
        _client = EbayBrowseClient(load_config())
    return _client


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@app.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ebay_search",
            description=(
                "Search eBay listings. Returns clean summaries of matching items "
                "including price, condition, seller ratings, and listing URL."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search terms, e.g. 'RTX 4090 founders edition'.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10, max 50).",
                        "default": 10,
                    },
                    "sort": {
                        "type": "string",
                        "description": "Sort order: bestMatch | price | -price | newlyListed",
                        "enum": ["bestMatch", "price", "-price", "newlyListed"],
                    },
                    "filter": {
                        "type": "string",
                        "description": "Raw eBay filter string, e.g. 'conditionIds:{1000}'.",
                    },
                    "category_ids": {
                        "type": "string",
                        "description": "Comma-separated eBay category IDs.",
                    },
                    "marketplace": {
                        "type": "string",
                        "description": "eBay marketplace ID (default EBAY_US).",
                        "default": "EBAY_US",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="ebay_get_item",
            description=(
                "Fetch full details for a single eBay item by its item ID "
                "(e.g. v1|123456789|0)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "eBay item ID.",
                    },
                    "marketplace": {
                        "type": "string",
                        "description": "eBay marketplace ID (default EBAY_US).",
                        "default": "EBAY_US",
                    },
                },
                "required": ["item_id"],
            },
        ),
        Tool(
            name="ebay_price_check",
            description=(
                "Search eBay and return an aggregated price landscape: count, "
                "min/median/max overall and broken down by condition, plus the "
                "cheapest listings. The headline tool for price research."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search terms, e.g. 'RTX 5080'.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Listings to sample (default 50, max 50).",
                        "default": 50,
                    },
                    "exclude": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Substrings to filter out of results (case-insensitive). "
                            "E.g. ['laptop', 'notebook'] to strip bundles."
                        ),
                    },
                    "marketplace": {
                        "type": "string",
                        "description": "eBay marketplace ID (default EBAY_US).",
                        "default": "EBAY_US",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_item_summary(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten an itemSummary into a clean dict."""
    price = item.get("price", {})
    seller = item.get("seller", {})
    return {
        "itemId": item.get("itemId", ""),
        "title": item.get("title", ""),
        "price": price.get("value", ""),
        "currency": price.get("currency", ""),
        "condition": item.get("condition", ""),
        "seller": {
            "username": seller.get("username", ""),
            "feedbackPercentage": seller.get("feedbackPercentage", ""),
            "feedbackScore": seller.get("feedbackScore", ""),
        },
        "itemWebUrl": item.get("itemWebUrl", ""),
        "location": item.get("itemLocation", {}).get("country", ""),
    }


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _round2(v: float) -> float:
    return round(v, 2)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

@app.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        text = await asyncio.to_thread(_dispatch, name, arguments)
        return [TextContent(type="text", text=text)]
    except EbayAPIError as e:
        return [TextContent(type="text", text=f"eBay API error {e.status}: {e.body}")]
    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:  # noqa: BLE001
        logger.exception("Unexpected error in tool %s", name)
        return [TextContent(type="text", text=f"Unexpected error: {e}")]


def _dispatch(name: str, args: dict[str, Any]) -> str:
    match name:
        case "ebay_search":
            return _do_search(args)
        case "ebay_get_item":
            return _do_get_item(args)
        case "ebay_price_check":
            return _do_price_check(args)
        case _:
            return f"Unknown tool: {name}"


def _do_search(args: dict[str, Any]) -> str:
    client = get_client()
    limit = min(int(args.get("limit", 10)), 50)
    data = client.search(
        args["query"],
        limit=limit,
        sort=args.get("sort"),
        filter=args.get("filter"),
        category_ids=args.get("category_ids"),
        marketplace=args.get("marketplace", "EBAY_US"),
    )
    items = [_extract_item_summary(i) for i in data.get("itemSummaries", [])]
    return json.dumps({"total": data.get("total", len(items)), "items": items}, indent=2)


def _do_get_item(args: dict[str, Any]) -> str:
    client = get_client()
    item_id = args["item_id"]
    data = client.get_item(item_id, marketplace=args.get("marketplace", "EBAY_US"))
    return json.dumps(data, indent=2)


def _do_price_check(args: dict[str, Any]) -> str:
    client = get_client()
    limit = min(int(args.get("limit", 50)), 50)
    exclude: list[str] = [s.lower() for s in (args.get("exclude") or [])]
    marketplace = args.get("marketplace", "EBAY_US")

    data = client.search(args["query"], limit=limit, marketplace=marketplace)
    summaries = data.get("itemSummaries", [])

    # Filter excluded titles
    if exclude:
        summaries = [
            s for s in summaries
            if not any(ex in s.get("title", "").lower() for ex in exclude)
        ]

    # Aggregate
    all_prices: list[float] = []
    currency = ""
    by_condition: dict[str, list[float]] = {}
    cheapest_items: list[dict[str, Any]] = []

    for item in summaries:
        price_val = item.get("price", {}).get("value")
        cond = item.get("condition", "Unknown")
        cur = item.get("price", {}).get("currency", "USD")
        if not currency:
            currency = cur
        try:
            price = float(price_val)
        except (TypeError, ValueError):
            continue
        all_prices.append(price)
        by_condition.setdefault(cond, []).append(price)
        cheapest_items.append({
            "price": _round2(price),
            "condition": cond,
            "title": item.get("title", ""),
            "itemWebUrl": item.get("itemWebUrl", ""),
        })

    cheapest_items.sort(key=lambda x: x["price"])

    by_cond_agg: dict[str, dict[str, Any]] = {}
    for cond, prices in sorted(by_condition.items()):
        by_cond_agg[cond] = {
            "count": len(prices),
            "min": _round2(min(prices)),
            "median": _round2(_median(prices)),
            "max": _round2(max(prices)),
        }

    result: dict[str, Any] = {
        "count": len(all_prices),
        "currency": currency or "USD",
        "min": _round2(min(all_prices)) if all_prices else None,
        "median": _round2(_median(all_prices)) if all_prices else None,
        "max": _round2(max(all_prices)) if all_prices else None,
        "by_condition": by_cond_agg,
        "cheapest": cheapest_items[:10],
    }
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the MCP server over stdio."""
    import argparse

    from ebay_mcp import __version__

    parser = argparse.ArgumentParser(
        prog="ebay-mcp",
        description="eBay Browse API MCP server (stdio). Read-only buy-side tools.",
    )
    parser.add_argument("--version", action="version", version=f"ebay-mcp {__version__}")
    parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(name)s - %(message)s")
    logger.info("Starting ebay-mcp server...")
    asyncio.run(_run())


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    main()
