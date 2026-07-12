"""Tests for DummyJSON fetcher."""

import pytest

from reachout.scripts import dummyjson_fetch


def test_fetch_products_offline():
    """Test that fetching products offline returns the cached list and has the correct shape."""
    products = dummyjson_fetch.fetch_products(cache_only=True)
    assert isinstance(products, list)
    assert len(products) > 0

    first_product = products[0]
    assert "title" in first_product
    assert "price" in first_product
    assert "category" in first_product
    assert "rating" in first_product
