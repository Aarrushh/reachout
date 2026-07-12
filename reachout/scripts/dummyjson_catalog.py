"""
Maps DummyJSON categories to our internal domain categories.
Why: DummyJSON has many specific categories, but our system strictly uses:
pharmacy, grocery, hardware, electronics, stationery. We must map the external
taxonomy to our internal one and drop categories we do not support.
"""

def map_category(dummyjson_category: str) -> str | None:
    """
    Map a DummyJSON category to an internal category.
    Returns None if the category is not supported.
    """
    match dummyjson_category:
        case "groceries":
            return "grocery"
        case "beauty" | "skin-care" | "fragrances":
            return "pharmacy"
        case "smartphones" | "laptops" | "tablets" | "mobile-accessories":
            return "electronics"
        case "furniture" | "home-decoration" | "kitchen-accessories" | "lighting" | "sports-accessories" | "motorcycle" | "vehicle":
            return "hardware"
        case _:
            return None
