import uuid
import json
import os
import jsonschema
from datetime import datetime, timedelta
from typing import List, Dict, Any

def load_schema(schema_name: str) -> dict:
    schema_path = os.path.join(os.path.dirname(__file__), "..", "shared", "schemas", schema_name)
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_iso_week_window(date_str: str) -> tuple[str, str]:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    # Monday is 0, Sunday is 6
    start = dt - timedelta(days=dt.weekday())
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()

def compute_signals(snapshots: List[Dict[str, Any]], category_map: Dict[str, str] = None, computed_at: str = None) -> List[Dict[str, Any]]:
    """
    Derives demand.demand_signals rows from raw trend snapshots.
    Pure Python derivation: windowed interest average, week-over-week delta %,
    direction, rank, and confidence labeling.
    """
    if category_map is None:
        category_map = {}
        
    if computed_at is None:
        computed_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        
    schema = load_schema("demand_signal.schema.json")
        
    # Phase 1: Group points into windows per keyword/geo
    kw_geo_windows = {}
    
    for snap in snapshots:
        kw = snap["keyword"]
        geo = snap["geo"]
        snap_id = snap["id"]
        
        key = (kw, geo)
        if key not in kw_geo_windows:
            kw_geo_windows[key] = {}
            
        for pt in snap["series"]:
            w_start, w_end = get_iso_week_window(pt["date"])
            w_key = (w_start, w_end)
            if w_key not in kw_geo_windows[key]:
                kw_geo_windows[key][w_key] = {"values": [], "snapshot_ids": set()}
            kw_geo_windows[key][w_key]["values"].append(pt["value"])
            kw_geo_windows[key][w_key]["snapshot_ids"].add(snap_id)
            
    # Compute interest_avg per window per keyword
    window_signals = {}
    
    for (kw, geo), windows in kw_geo_windows.items():
        sorted_window_keys = sorted(windows.keys()) # Sorts chronologically
        
        # Check for provider gaps
        has_gap = False
        for i in range(1, len(sorted_window_keys)):
            prev_end = datetime.strptime(sorted_window_keys[i-1][1], "%Y-%m-%d").date()
            curr_start = datetime.strptime(sorted_window_keys[i][0], "%Y-%m-%d").date()
            if (curr_start - prev_end).days > 1:
                has_gap = True
                
        series_data = []
        for w_key in sorted_window_keys:
            vals = windows[w_key]["values"]
            avg = round(sum(vals) / len(vals), 2) if vals else 0.0
            series_data.append({
                "window_start": w_key[0],
                "window_end": w_key[1],
                "interest_avg": avg,
                "snapshot_ids": sorted(list(windows[w_key]["snapshot_ids"]))
            })
            
        # Compute delta_pct and direction
        for i in range(len(series_data)):
            curr = series_data[i]
            
            delta_pct = 0.0
            if i > 0:
                prev_avg = series_data[i-1]["interest_avg"]
                if prev_avg > 0:
                    delta_pct = round(((curr["interest_avg"] - prev_avg) / prev_avg) * 100, 2)
                elif curr["interest_avg"] > 0:
                    delta_pct = 100.0
            
            curr["delta_pct"] = float(delta_pct)
            
            if delta_pct >= 15.0:
                direction = "rising"
            elif delta_pct <= -15.0:
                direction = "falling"
            else:
                direction = "flat"
                
            curr["direction"] = direction
            
        # Compute confidence
        for i in range(len(series_data)):
            curr = series_data[i]
            weeks_of_data = i + 1
            
            if has_gap:
                confidence = "low"
            else:
                stable_direction = False
                if weeks_of_data >= 3:
                    dir_current = curr["direction"]
                    dir_prev1 = series_data[i-1]["direction"]
                    dir_prev2 = series_data[i-2]["direction"]
                    stable_direction = (dir_current == dir_prev1 == dir_prev2)
                    
                if weeks_of_data >= 8 and curr["interest_avg"] >= 20.0 and stable_direction:
                    confidence = "high"
                elif weeks_of_data >= 4 and curr["interest_avg"] >= 10.0:
                    confidence = "medium"
                else:
                    confidence = "low"
                    
            curr["confidence"] = confidence
            curr["keyword"] = kw
            curr["geo"] = geo
            curr["category"] = category_map.get(kw, None)
            
            w_key = (curr["window_start"], curr["window_end"])
            if w_key not in window_signals:
                window_signals[w_key] = []
            window_signals[w_key].append(curr)
            
    final_signals = []
    
    # Compute rank per window and assemble final signals
    for w_key, signals in window_signals.items():
        # Sort by interest_avg descending, then keyword ascending
        signals.sort(key=lambda x: (-x["interest_avg"], x["keyword"]))
        
        rank = 1
        for i in range(len(signals)):
            if i > 0 and signals[i]["interest_avg"] < signals[i-1]["interest_avg"]:
                rank += 1
                
            signal = {
                "id": str(uuid.uuid4()),
                "keyword": signals[i]["keyword"],
                "category": signals[i]["category"],
                "geo": signals[i]["geo"],
                "window_start": signals[i]["window_start"],
                "window_end": signals[i]["window_end"],
                "interest_avg": float(signals[i]["interest_avg"]),
                "delta_pct": signals[i]["delta_pct"],
                "direction": signals[i]["direction"],
                "rank": rank,
                "confidence": signals[i]["confidence"],
                "snapshot_ids": signals[i]["snapshot_ids"],
                "computed_at": computed_at
            }
            
            # Validate against schema
            jsonschema.validate(instance=signal, schema=schema)
            final_signals.append(signal)
            
    # Deterministic final sort: by window_start, then rank, then keyword
    final_signals.sort(key=lambda x: (x["window_start"], x["rank"], x["keyword"]))
    
    return final_signals
