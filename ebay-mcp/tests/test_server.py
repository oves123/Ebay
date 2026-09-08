"""Server-layer tests: tool listing, dispatch, and price aggregation.

No live network calls — EbayBrowseClient is replaced with a fake.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import ebay_mcp.server as server
from ebay_mcp.server import _dispatch, _median

# ---------------------------------------------------------------------------
# Median helper
# ---------------------------------------------------------------------------

def test_median_odd():
    assert _median([1.0, 3.0, 2.0]) == 2.0


def test_median_even():
    assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_median_single():
    assert _median([7.0]) == 7.0


def test_median_empty():
    assert _median([]) == 0.0


# ---------------------------------------------------------------------------
# Tool listing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_tools_returns_three():
    tools = await server.list_tools()
    names = [t.name for t in tools]
    assert "ebay_search" in names
    assert "ebay_get_item" in names
    assert "ebay_price_check" in names
    assert len(tools) == 3


@pytest.mark.asyncio
async def test_all_tools_have_required_fields():
    tools = await server.list_tools()
    for t in tools:
        assert t.name
        assert t.description
        assert t.inputSchema


# ---------------------------------------------------------------------------
# Fixture: fake Browse client
# ---------------------------------------------------------------------------

SAMPLE_ITEMS = [
    {
        "itemId": "v1|111|0",
        "title": "RTX 5080 Founders Edition",
        "price": {"value": "1099.99", "currency": "USD"},
        "condition": "New",
        "seller": {"username": "seller1", "feedbackPercentage": "99.8", "feedbackScore": 5000},
        "itemWebUrl": "https://www.ebay.com/itm/111",
        "itemLocation": {"country": "US"},
    },
    {
        "itemId": "v1|222|0",
        "title": "RTX 5080 Used Good Shape",
        "price": {"value": "899.00", "currency": "USD"},
        "condition": "Used",
        "seller": {"username": "seller2", "feedbackPercentage": "98.5", "feedbackScore": 300},
        "itemWebUrl": "https://www.ebay.com/itm/222",
        "itemLocation": {"country": "US"},
    },
    {
        "itemId": "v1|333|0",
        "title": "RTX 5080 laptop bundle",
        "price": {"value": "1400.00", "currency": "USD"},
        "condition": "New",
        "seller": {"username": "seller3", "feedbackPercentage": "97.0", "feedbackScore": 100},
        "itemWebUrl": "https://www.ebay.com/itm/333",
        "itemLocation": {"country": "US"},
    },
]


@pytest.fixture()
def fake_client(monkeypatch):
    client = MagicMock()
    client.search.return_value = {
        "total": len(SAMPLE_ITEMS),
        "itemSummaries": SAMPLE_ITEMS,
    }
    monkeypatch.setattr(server, "get_client", lambda: client)
    return client


# ---------------------------------------------------------------------------
# ebay_search dispatch
# ---------------------------------------------------------------------------

def test_ebay_search_returns_items(fake_client):
    result = json.loads(_dispatch("ebay_search", {"query": "RTX 5080"}))
    assert result["total"] == 3
    assert len(result["items"]) == 3
    item = result["items"][0]
    assert item["itemId"] == "v1|111|0"
    assert item["price"] == "1099.99"
    assert item["seller"]["username"] == "seller1"


def test_ebay_search_caps_limit(fake_client):
    _dispatch("ebay_search", {"query": "RTX 5080", "limit": 999})
    call_kwargs = fake_client.search.call_args
    assert call_kwargs.kwargs["limit"] == 50


def test_ebay_search_passes_sort(fake_client):
    _dispatch("ebay_search", {"query": "RTX 5080", "sort": "price"})
    assert fake_client.search.call_args.kwargs["sort"] == "price"


# ---------------------------------------------------------------------------
# ebay_get_item dispatch
# ---------------------------------------------------------------------------

def test_ebay_get_item(fake_client):
    fake_client.get_item.return_value = {"itemId": "v1|111|0", "title": "RTX 5080"}
    result = json.loads(_dispatch("ebay_get_item", {"item_id": "v1|111|0"}))
    assert result["itemId"] == "v1|111|0"
    fake_client.get_item.assert_called_once_with("v1|111|0", marketplace="EBAY_US")


# ---------------------------------------------------------------------------
# ebay_price_check dispatch
# ---------------------------------------------------------------------------

def test_price_check_aggregates_correctly(fake_client):
    result = json.loads(_dispatch("ebay_price_check", {"query": "RTX 5080"}))
    assert result["count"] == 3
    assert result["currency"] == "USD"
    assert result["min"] == 899.0
    assert result["max"] == 1400.0
    # median of [899, 1099.99, 1400] = 1099.99
    assert result["median"] == 1099.99
    assert "New" in result["by_condition"]
    assert "Used" in result["by_condition"]
    assert result["by_condition"]["Used"]["count"] == 1
    assert result["by_condition"]["New"]["count"] == 2


def test_price_check_exclude_filters(fake_client):
    result = json.loads(_dispatch("ebay_price_check", {
        "query": "RTX 5080",
        "exclude": ["laptop"],
    }))
    # "RTX 5080 laptop bundle" should be excluded
    assert result["count"] == 2
    titles = [c["title"] for c in result["cheapest"]]
    assert not any("laptop" in t.lower() for t in titles)


def test_price_check_cheapest_capped_at_10(fake_client):
    result = json.loads(_dispatch("ebay_price_check", {"query": "RTX 5080"}))
    assert len(result["cheapest"]) <= 10


def test_price_check_cheapest_sorted(fake_client):
    result = json.loads(_dispatch("ebay_price_check", {"query": "RTX 5080"}))
    prices = [c["price"] for c in result["cheapest"]]
    assert prices == sorted(prices)


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------

def test_unknown_tool():
    assert "Unknown tool" in _dispatch("bogus_tool", {})
