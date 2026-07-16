import pytest
from api.chat import _system_prompt

def test_system_prompt_contents():
    store = {
        "name": "Supermercado Paco",
        "neighbourhood": "Chamberí",
        "avg_delivery_mins": 15
    }
    products = [
        {"name": "Manzanas", "price": 2.50, "stock_qty": 50},
        {"name": "Agua mineral", "price": 0.80, "stock_qty": 100},
        {"name": "Pan", "price": 1.00, "stock_qty": 0}
    ]
    
    prompt = _system_prompt(store, products)
    
    # Assert store name and neighbourhood in the persona line
    assert "You are Supermercado Paco, a friendly local shopkeeper in Chamberí, Madrid." in prompt
    
    # Assert inventory items formatting including stock-0 rows
    assert "- Manzanas — 2.5€ (stock: 50)" in prompt
    assert "- Agua mineral — 0.8€ (stock: 100)" in prompt
    assert "- Pan — 1.0€ (stock: 0)" in prompt
    
    # Assert avg_delivery_mins value is present
    assert "Average delivery: 15 minutes." in prompt
    
    # Assert under-3-sentences instruction
    assert "Keep replies under 3 sentences." in prompt
