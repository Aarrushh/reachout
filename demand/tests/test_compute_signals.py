import json
import os
import uuid
from demand.scripts.compute_signals import compute_signals

def test_compute_signals_byte_for_byte(monkeypatch):
    # Monkeypatch uuid to be deterministic to match expected output
    class IncrementalUUID:
        def __init__(self):
            self.counter = 0
            
        def __call__(self):
            self.counter += 1
            hex_str = f"{self.counter:032x}"
            return uuid.UUID(hex_str)
            
    monkeypatch.setattr(uuid, "uuid4", IncrementalUUID())
    
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "signals")
    
    with open(os.path.join(fixtures_dir, "input_snapshots.json"), "r", encoding="utf-8") as f:
        snapshots = json.load(f)
        
    with open(os.path.join(fixtures_dir, "expected_signals.json"), "r", encoding="utf-8") as f:
        expected_signals = json.load(f)
        
    category_map = {
        "high_kw": "HighCat",
        "medium_kw": "MedCat",
        "short_kw": "ShortCat",
        "gap_kw": "GapCat",
        "boundary_kw": "BoundCat"
    }
    
    # Compute signals
    actual_signals = compute_signals(snapshots, category_map=category_map, computed_at="2023-11-20T12:00:00Z")
    
    # Assert exact match (the compute_signals function also validates against the schema internally)
    assert actual_signals == expected_signals

def test_edge_cases_and_tiers():
    # Read the expected signals directly to assert on the final row for each keyword
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "signals")
    with open(os.path.join(fixtures_dir, "expected_signals.json"), "r", encoding="utf-8") as f:
        signals = json.load(f)
        
    # Get the LAST signal for each keyword
    last_signals = {}
    for s in signals:
        last_signals[s["keyword"]] = s
        
    high = last_signals["high_kw"]
    assert high["confidence"] == "high"
    assert high["direction"] == "rising"
    
    medium = last_signals["medium_kw"]
    assert medium["confidence"] == "medium"
    
    short = last_signals["short_kw"]
    assert short["confidence"] == "low"
    
    gap = last_signals["gap_kw"]
    assert gap["confidence"] == "low"
    
    bound = last_signals["boundary_kw"]
    # For boundary kw, the last point was a -15% drop, so it should be falling
    assert bound["delta_pct"] == -15.0
    assert bound["direction"] == "falling"
    
    # Let's also check the point before the last for boundary_kw to ensure +15% is rising
    bound_signals = [s for s in signals if s["keyword"] == "boundary_kw"]
    # The middle point is index 1
    assert bound_signals[1]["delta_pct"] == 15.0
    assert bound_signals[1]["direction"] == "rising"

