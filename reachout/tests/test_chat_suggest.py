import pytest
from reachout.api.chat import _suggest

def test_suggest_mentions_ordered_and_capped():
    products = [
        {"name": "Café Mocca", "tags": [], "stock_qty": 5},
        {"name": "Zumo de Naranja", "tags": [], "stock_qty": 2},
        {"name": "Croissant", "tags": [], "stock_qty": 10},
        {"name": "Té Verde", "tags": [], "stock_qty": 0},
    ]

    # Accent/case-insensitive matching, ordered by appearance.
    reply = "Tenemos zumo de Naranja y también café MOCCA y Croissant."
    # Zumo de Naranja (first), Café Mocca (second), Croissant (third)
    res = _suggest(reply, "quiero algo", products)
    assert len(res) == 3
    assert res[0]["name"] == "Zumo de Naranja"
    assert res[1]["name"] == "Café Mocca"
    assert res[2]["name"] == "Croissant"
    
    # Mention match capping at 3
    products.append({"name": "Agua", "tags": [], "stock_qty": 5})
    reply_4 = "Tenemos cafe mocca, zumo de naranja, croissant, y agua."
    res2 = _suggest(reply_4, "algo", products)
    assert len(res2) == 3
    assert res2[0]["name"] == "Café Mocca"
    assert res2[1]["name"] == "Zumo de Naranja"
    assert res2[2]["name"] == "Croissant"

def test_suggest_fallback_stock_qty():
    products = [
        {"name": "Café", "tags": ["caliente", "bebida"], "stock_qty": 5},
        {"name": "Té", "tags": ["caliente", "bebida"], "stock_qty": 0}, # out of stock
        {"name": "Refresco", "tags": ["frio", "bebida", "soda"], "stock_qty": 2},
    ]

    # No mention in reply, keyword fallback on message
    # message tokens: \w{4,} -> 'caliente'
    reply = "No sé de qué hablas."
    message = "quiero algo caliente"
    res = _suggest(reply, message, products)
    
    # Té is out of stock, so only Café should be matched.
    assert len(res) == 1
    assert res[0]["name"] == "Café"

    # Multiple keyword matches
    message2 = "quiero una bebida caliente o una soda o un refresco"
    res2 = _suggest(reply, message2, products)
    assert len(res2) == 2
    # Refresco matches: bebida, soda, refresco (3 hits)
    # Café matches: bebida, caliente (2 hits)
    # Refresco should be first due to more hits
    assert res2[0]["name"] == "Refresco"
    assert res2[1]["name"] == "Café"

def test_suggest_no_matches():
    products = [
        {"name": "Café", "tags": [], "stock_qty": 5},
    ]
    res = _suggest("Hola", "nada", products)
    assert res == []
