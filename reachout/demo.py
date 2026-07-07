"""Live end-to-end demo — Madrid.

Loads real Madrid shops (live Overpass, falling back to the committed
offline cache), starts the inventory simulator in a background thread so
stock keeps moving, then fires a few bilingual searches a couple of seconds
apart. You will see stock change between searches and pings land at shops
in real time.

    python demo.py
    REACHOUT_OFFLINE=1 python demo.py   # no network at all

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

import db                              # noqa: E402
import osm_ingest                      # noqa: E402
from inventory_simulator import run_simulator  # noqa: E402
import run_pipeline                    # noqa: E402

# Puerta del Sol: central enough to reach shops of every category.
USER_LAT, USER_LNG = 40.4168, -3.7038
RADIUS_KM = 3.0
QUERIES = [
    "algo para el dolor de cabeza",
    "usb c charger",
    "leche y pan",
    "cuaderno y bolígrafo",
]


def main():
    print("Loading Madrid shops (live Overpass, falling back to the committed cache)...")
    conn = db.connect()
    try:
        osm_ingest.ingest(conn=conn)
    finally:
        conn.close()

    print("Starting live inventory simulator in the background...\n")
    stop = threading.Event()
    sim = threading.Thread(target=run_simulator, kwargs={"stop_event": stop, "interval": 0.4}, daemon=True)
    sim.start()

    try:
        for q in QUERIES:
            time.sleep(2)  # let inventory move between searches
            print("=" * 70)
            try:
                run_pipeline.run(q, lat=USER_LAT, lng=USER_LNG, radius_km=RADIUS_KM)
            except run_pipeline.PipelineError as e:
                print(f"[HALTED] {e}")
    finally:
        stop.set()
        sim.join(timeout=2)
        print("=" * 70)
        print("Demo complete. Inventory simulator stopped.")
        print("Look in data/notifications/ to see the pings each shop received.")


if __name__ == "__main__":
    main()
