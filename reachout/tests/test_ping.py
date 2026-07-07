import json

from ping import ping


def _match(shop_id="osm:node:111", shop_name="Farmacia Sol", distance_km=0.4):
    return {
        "shop_id": shop_id,
        "shop_name": shop_name,
        "distance_km": distance_km,
        "items": [
            {"sku": "PHA-0001", "name": "Paracetamol", "category": "pharmacy",
             "price": 3.95, "currency": "EUR", "qty": 5},
        ],
    }


def _intent(raw_query="paracetamol", keywords=None):
    return {"raw_query": raw_query, "keywords": keywords or ["paracetamol"]}


def test_ping_appends_one_line_to_shop_inbox(tmp_path):
    notif_dir = tmp_path / "notifications"
    match = _match()
    intent = _intent()

    payload = ping(match, intent, notif_dir=str(notif_dir))

    inbox = notif_dir / "osm_node_111.jsonl"
    assert inbox.exists()
    lines = inbox.read_text().strip().splitlines()
    assert len(lines) == 1
    logged = json.loads(lines[0])
    assert logged["shop_id"] == "osm:node:111"
    assert logged["query"] == "paracetamol"
    assert logged["distance_km"] == 0.4
    assert logged["matched_items"][0]["sku"] == "PHA-0001"
    assert payload == logged


def test_ping_appends_second_line_on_second_call(tmp_path):
    notif_dir = tmp_path / "notifications"
    match = _match()
    intent = _intent()

    ping(match, intent, notif_dir=str(notif_dir))
    ping(match, intent, notif_dir=str(notif_dir))

    inbox = notif_dir / "osm_node_111.jsonl"
    lines = inbox.read_text().strip().splitlines()
    assert len(lines) == 2
