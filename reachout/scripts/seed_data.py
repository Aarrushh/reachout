"""Seeds sample shops and their starting inventory.

Shops are placed around Mumbai because that is the demo location. The
coordinates are real-ish points spread across a few kilometres so the
radius filter has something to do. Inventory is fixed and known. Nothing
here is invented at runtime by an AI. This is the ground truth the rest
of the system reads from.

Run once: python scripts/seed_data.py
"""

import json
import os
import time

import db

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

# Eight sample shops spread across Mumbai. Lat/lng are approximate points.
SHOPS = [
    {"id": "shop_01", "name": "Andheri Care Pharmacy", "category": "pharmacy",
     "lat": 19.1197, "lng": 72.8468, "address": "Andheri West"},
    {"id": "shop_02", "name": "Bandra Daily Grocers", "category": "grocery",
     "lat": 19.0596, "lng": 72.8295, "address": "Bandra West"},
    {"id": "shop_03", "name": "Powai Tech Corner", "category": "electronics",
     "lat": 19.1176, "lng": 72.9060, "address": "Powai"},
    {"id": "shop_04", "name": "Dadar Stationery Mart", "category": "stationery",
     "lat": 19.0178, "lng": 72.8478, "address": "Dadar"},
    {"id": "shop_05", "name": "Worli Health Chemist", "category": "pharmacy",
     "lat": 19.0176, "lng": 72.8170, "address": "Worli"},
    {"id": "shop_06", "name": "Kurla Fresh Mart", "category": "grocery",
     "lat": 19.0726, "lng": 72.8845, "address": "Kurla"},
    {"id": "shop_07", "name": "Vile Parle Gadget Hub", "category": "electronics",
     "lat": 19.0990, "lng": 72.8470, "address": "Vile Parle"},
    {"id": "shop_08", "name": "Matunga Book & Pen", "category": "stationery",
     "lat": 19.0270, "lng": 72.8570, "address": "Matunga"},
]

# A catalogue per category. The simulator draws from these when it adds or
# restocks items. SKUs and names are fixed so search has stable targets.
CATALOGUE = {
    "pharmacy": [
        ("PARA500", "Paracetamol 500mg strip", 25.0),
        ("IBU400", "Ibuprofen 400mg strip", 40.0),
        ("ORS01", "ORS hydration sachet", 18.0),
        ("BAND01", "Adhesive bandage pack", 55.0),
        ("VITC01", "Vitamin C tablets", 120.0),
        ("COUGH01", "Cough syrup 100ml", 95.0),
    ],
    "grocery": [
        ("MILK1L", "Toned milk 1 litre", 64.0),
        ("BREAD01", "Whole wheat bread loaf", 45.0),
        ("EGG12", "Eggs dozen", 84.0),
        ("RICE5", "Basmati rice 5kg", 520.0),
        ("OIL1L", "Sunflower oil 1 litre", 165.0),
        ("SUGAR1", "Sugar 1kg", 48.0),
    ],
    "electronics": [
        ("USBC1M", "USB-C cable 1m", 199.0),
        ("CHG20W", "20W fast charger", 899.0),
        ("EARBUD", "Wireless earbuds", 1799.0),
        ("PWRBNK", "10000mAh power bank", 1299.0),
        ("HDMI2M", "HDMI cable 2m", 349.0),
        ("MOUSE1", "Wireless mouse", 649.0),
    ],
    "stationery": [
        ("A4REAM", "A4 paper ream", 320.0),
        ("PEN10", "Blue pen pack of 10", 90.0),
        ("NOTE200", "200 page notebook", 75.0),
        ("MARKER4", "Marker set of 4", 140.0),
        ("STAPLE1", "Stapler", 180.0),
        ("GLUE1", "Glue stick", 35.0),
    ],
}


def seed():
    os.makedirs(DATA_DIR, exist_ok=True)
    db.init_db()
    conn = db.connect()

    # Wipe any previous run so seeding is repeatable.
    conn.execute("DELETE FROM inventory")
    conn.execute("DELETE FROM shops")

    for shop in SHOPS:
        db.upsert_shop(conn, shop)
        # Give each shop the four most common items in its category to start.
        for sku, name, price in CATALOGUE[shop["category"]][:4]:
            db.upsert_item(conn, {
                "shop_id": shop["id"], "sku": sku, "name": name,
                "category": shop["category"], "price": price, "qty": 20,
            })
    conn.commit()
    conn.close()

    # Also write a plain JSON copy of shops for easy inspection.
    with open(os.path.join(DATA_DIR, "shops.json"), "w") as f:
        json.dump(SHOPS, f, indent=2)

    print("Seeded", len(SHOPS), "shops with starting inventory at", time.strftime("%H:%M:%S"))


if __name__ == "__main__":
    seed()
