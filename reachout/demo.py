"""Live end-to-end demo.

Starts the inventory simulator in a background thread so stock keeps moving,
then fires a few searches a couple of seconds apart. You will see stock
change between searches and pings land at shops in real time.

    python demo.py

This is the whole product in miniature: live inventory on one side, a
shopper searching on the other, and an instant ping connecting them.
"""

import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scripts"))
sys.path.insert(0, os.path.join(HERE, "agent"))

import seed_data
from inventory_simulator import run_simulator
import run_pipeline

# A shopper near Bandra/Mahim, central enough to reach all shop categories.
USER_LAT, USER_LNG = 19.06, 72.83
QUERIES = ["something for a headache", "usb c charger", "milk and bread", "notebook and pen"]


def main():
    print("Seeding sample data...")
    seed_data.seed()

    print("Starting live inventory simulator in the background...\n")
    stop = threading.Event()
    sim = threading.Thread(target=run_simulator, kwargs={"stop_event": stop, "interval": 0.4}, daemon=True)
    sim.start()

    try:
        for q in QUERIES:
            time.sleep(2)  # let inventory move between searches
            print("=" * 70)
            run_pipeline.run(q, USER_LAT, USER_LNG, radius_km=5.0, use_llm=False)
    finally:
        stop.set()
        sim.join(timeout=2)
        print("=" * 70)
        print("Demo complete. Inventory simulator stopped.")
        print("Look in data/notifications/ to see the pings each shop received.")


if __name__ == "__main__":
    main()
