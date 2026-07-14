"""Tests for the live verification script."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts.verify_live import (
    assert_health_simulator,
    assert_inventory_page_walk,
    assert_regions_count,
    assert_stream_yields_stock,
)


def test_assert_health_simulator_success():
    """Test health check passes when simulator is running."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok", "simulator_running": True}
        mock_get.return_value = mock_resp
        
        # Should not raise
        assert_health_simulator("http://dummy")
        mock_get.assert_called_once_with("http://dummy/api/health", timeout=10)


def test_assert_health_simulator_failure():
    """Test health check fails when simulator is not running."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok", "simulator_running": False}
        mock_get.return_value = mock_resp
        
        with pytest.raises(AssertionError, match="simulator is not running"):
            assert_health_simulator("http://dummy")


def test_assert_regions_count_success():
    """Test regions count passes when >= 20."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok", "region_count": 25}
        mock_get.return_value = mock_resp
        
        # Should not raise
        assert_regions_count("http://dummy")
        mock_get.assert_called_once_with("http://dummy/api/regions", timeout=10)


def test_assert_regions_count_failure():
    """Test regions count fails when < 20."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok", "region_count": 5}
        mock_get.return_value = mock_resp
        
        with pytest.raises(AssertionError, match="Expected >= 20 regions"):
            assert_regions_count("http://dummy")


def test_assert_inventory_page_walk_success():
    """Test inventory pagination passes when pages are distinct and valid."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        mock_resp1 = MagicMock()
        mock_resp1.json.return_value = {
            "status": "ok",
            "total_pages": 2,
            "items": [{"sku": "ITM-0001"}]
        }
        
        mock_resp2 = MagicMock()
        mock_resp2.json.return_value = {
            "status": "ok",
            "total_pages": 2,
            "items": [{"sku": "ITM-0002"}]
        }
        
        mock_get.side_effect = [mock_resp1, mock_resp2]
        
        # Should not raise
        assert_inventory_page_walk("http://dummy")
        
        assert mock_get.call_count == 2
        mock_get.assert_any_call("http://dummy/api/inventory", params={"page": 1, "page_size": 10}, timeout=10)
        mock_get.assert_any_call("http://dummy/api/inventory", params={"page": 2, "page_size": 10}, timeout=10)


def test_assert_inventory_page_walk_single_page():
    """Test inventory pagination passes when there's only 1 page."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        mock_resp1 = MagicMock()
        mock_resp1.json.return_value = {
            "status": "ok",
            "total_pages": 1,
            "items": [{"sku": "ITM-0001"}]
        }
        mock_get.return_value = mock_resp1
        
        # Should not raise
        assert_inventory_page_walk("http://dummy")
        assert mock_get.call_count == 1


def test_assert_inventory_page_walk_failure_empty_page():
    """Test inventory pagination fails when a page is empty."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        mock_resp1 = MagicMock()
        mock_resp1.json.return_value = {
            "status": "ok",
            "total_pages": 2,
            "items": []
        }
        mock_get.return_value = mock_resp1
        
        with pytest.raises(AssertionError, match="got an empty list"):
            assert_inventory_page_walk("http://dummy")


def test_assert_inventory_page_walk_failure_identical_pages():
    """Test inventory pagination fails when two pages have identical items."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        items = [{"sku": "ITM-0001"}]
        mock_resp1 = MagicMock()
        mock_resp1.json.return_value = {
            "status": "ok",
            "total_pages": 2,
            "items": items
        }
        mock_resp2 = MagicMock()
        mock_resp2.json.return_value = {
            "status": "ok",
            "total_pages": 2,
            "items": items
        }
        mock_get.side_effect = [mock_resp1, mock_resp2]
        
        with pytest.raises(AssertionError, match="identical list of items"):
            assert_inventory_page_walk("http://dummy")


def test_assert_stream_yields_stock_success():
    """Test stream verification passes when a stock event is yielded."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        mock_resp = MagicMock()
        # Note: iter_lines returns bytes
        mock_resp.iter_lines.return_value = [
            b"event: hello",
            b"data: {}",
            b"",
            b"event: stock",
            b"data: {\"sku\": \"ITM-0001\"}",
            b""
        ]
        
        # context manager support
        mock_resp.__enter__.return_value = mock_resp
        mock_get.return_value = mock_resp
        
        # Should not raise
        assert_stream_yields_stock("http://dummy", timeout=5)


def test_assert_stream_yields_stock_timeout():
    """Test stream verification fails when it doesn't yield a stock event within timeout."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            b"event: hello",
            b"data: {}",
            b"",
            b": keep-alive",
            b"",
        ]
        mock_resp.__enter__.return_value = mock_resp
        mock_get.return_value = mock_resp
        
        with pytest.raises(AssertionError, match="Stream closed without yielding"):
            assert_stream_yields_stock("http://dummy", timeout=1)


def test_assert_stream_yields_stock_request_exception():
    """Test stream verification fails on connection errors."""
    with patch("scripts.verify_live.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        with pytest.raises(AssertionError, match="Stream connection failed"):
            assert_stream_yields_stock("http://dummy", timeout=1)
