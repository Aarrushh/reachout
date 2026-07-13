from scripts.dummyjson_catalog import map_category

def test_map_category_grocery():
    assert map_category("groceries") == "grocery"

def test_map_category_pharmacy():
    assert map_category("beauty") == "pharmacy"
    assert map_category("skin-care") == "pharmacy"
    assert map_category("fragrances") == "pharmacy"

def test_map_category_electronics():
    assert map_category("smartphones") == "electronics"
    assert map_category("laptops") == "electronics"
    assert map_category("tablets") == "electronics"
    assert map_category("mobile-accessories") == "electronics"

def test_map_category_hardware():
    assert map_category("furniture") == "hardware"
    assert map_category("home-decoration") == "hardware"
    assert map_category("kitchen-accessories") == "hardware"
    assert map_category("lighting") == "hardware"
    assert map_category("sports-accessories") == "hardware"
    assert map_category("motorcycle") == "hardware"
    assert map_category("vehicle") == "hardware"

def test_map_category_none_cases():
    assert map_category("apparel") is None
    assert map_category("jewellery") is None
    assert map_category("watches") is None
    assert map_category("bags") is None
    assert map_category("sunglasses") is None
    assert map_category("mens-shirts") is None
    assert map_category("womens-dresses") is None

def test_map_category_no_stationery():
    # Explicitly verify that no input to map_category returns 'stationery'
    # By ensuring that our exhaustive list of known dummyjson categories
    # don't return stationery, and relying on our code review that `map_category`
    # only returns the 4 listed categories or None.
    
    # We can also assert that passing 'stationery' itself returns None
    # since it's not a dummyjson category we map.
    assert map_category("stationery") is None
    
    categories = [
        "groceries", "beauty", "skin-care", "fragrances", 
        "smartphones", "laptops", "tablets", "mobile-accessories",
        "furniture", "home-decoration", "kitchen-accessories", 
        "lighting", "sports-accessories", "motorcycle", "vehicle",
        "apparel", "jewellery", "watches", "bags", "sunglasses"
    ]
    for cat in categories:
        assert map_category(cat) != "stationery"
