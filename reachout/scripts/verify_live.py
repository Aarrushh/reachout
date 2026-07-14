"""Live end-to-end verification script.

This script tests a running ReachOut server (started with REACHOUT_SIM=1).
It asserts that the health endpoint reports the simulator is running,
that there are at least 20 regions, that the inventory endpoint pages
correctly, and that the SSE stream yields a stock event within 30 seconds.
"""

import argparse
import sys
import time

import requests

def assert_health_simulator(base_url: str):
    """Verify that the health endpoint reports the simulator is running."""
    url = f"{base_url}/api/health"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("simulator_running", False):
        raise AssertionError("Health endpoint indicates simulator is not running (simulator_running=False). Did you start the server with REACHOUT_SIM=1?")


def assert_regions_count(base_url: str):
    """Verify that there are at least 20 regions."""
    url = f"{base_url}/api/regions"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    count = data.get("region_count", 0)
    if count < 20:
        raise AssertionError(f"Expected >= 20 regions, got {count}.")


def assert_inventory_page_walk(base_url: str):
    """Verify that the inventory endpoint pages correctly."""
    url = f"{base_url}/api/inventory"
    
    # Page 1
    resp1 = requests.get(url, params={"page": 1, "page_size": 10}, timeout=10)
    resp1.raise_for_status()
    data1 = resp1.json()
    
    total_pages = data1.get("total_pages", 0)
    if total_pages < 1:
        raise AssertionError(f"Expected total_pages >= 1, got {total_pages}.")
        
    items1 = data1.get("items", [])
    if not items1:
        raise AssertionError("Expected page 1 to have items, got an empty list.")
        
    if total_pages > 1:
        # Page 2
        resp2 = requests.get(url, params={"page": 2, "page_size": 10}, timeout=10)
        resp2.raise_for_status()
        data2 = resp2.json()
        
        items2 = data2.get("items", [])
        if not items2:
            raise AssertionError("Expected page 2 to have items, got an empty list.")
            
        # Check that items are different
        if items1 == items2:
            raise AssertionError("Page 1 and Page 2 returned the identical list of items.")


def assert_stream_yields_stock(base_url: str, timeout: int = 30):
    """Verify that the SSE stream yields a stock event within `timeout` seconds."""
    url = f"{base_url}/api/inventory/stream"
    start_time = time.time()
    
    try:
        with requests.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if time.time() - start_time > timeout:
                    raise AssertionError(f"No stock event received within {timeout} seconds.")
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("event: stock"):
                        return  # Success
    except requests.exceptions.ReadTimeout:
        raise AssertionError(f"Read timeout while waiting for stock event within {timeout} seconds.")
    except requests.exceptions.RequestException as e:
        raise AssertionError(f"Stream connection failed: {e}")

    raise AssertionError(f"Stream closed without yielding a stock event within {timeout} seconds.")


def run_all(base_url: str) -> bool:
    """Run all assertions and return True if all passed."""
    assertions = [
        ("Health & Simulator", assert_health_simulator),
        ("Regions Count", assert_regions_count),
        ("Inventory Pagination", assert_inventory_page_walk),
        ("SSE Stream Stock Event", assert_stream_yields_stock),
    ]
    
    all_passed = True
    print(f"Testing ReachOut server at {base_url}...")
    
    for name, func in assertions:
        print(f"Running '{name}'... ", end="", flush=True)
        try:
            func(base_url)
            print("OK")
        except AssertionError as e:
            print(f"FAILED\n  {e}")
            all_passed = False
        except Exception as e:
            print(f"ERROR\n  {e}")
            all_passed = False
            
    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live end-to-end verification script for ReachOut.")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the ReachOut server (default: http://localhost:8000)")
    args = parser.parse_args()
    
    success = run_all(args.url)
    if not success:
        print("\nVerification failed.")
        sys.exit(1)
    
    print("\nAll verifications passed.")
    sys.exit(0)
