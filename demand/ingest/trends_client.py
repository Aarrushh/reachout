import json
import os
import time
from typing import Any, Dict, List, Protocol

class TrendsProvider(Protocol):
    def interest_over_time(self, keywords: List[str], geo: str, timeframe: str) -> Dict[str, List[Dict[str, Any]]]:
        ...

    def interest_by_region(self, keyword: str, geo: str) -> List[Dict[str, Any]]:
        ...

def retry_on_429(max_retries: int = 3, base_delay: int = 1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    is_429 = False
                    if hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429:
                        is_429 = True
                    elif '429' in str(e):
                        is_429 = True
                    
                    if is_429 and retries < max_retries:
                        delay = base_delay * (2 ** retries)
                        time.sleep(delay)
                        retries += 1
                    else:
                        raise e
        return wrapper
    return decorator

class TrendspyProvider:
    @retry_on_429()
    def interest_over_time(self, keywords: List[str], geo: str = "ES-MD", timeframe: str = "today 1-m") -> Dict[str, List[Dict[str, Any]]]:
        import pandas as pd
        import trendspy
        
        client = trendspy.Trends()
        df = client.interest_over_time(keywords, geo=geo, timeframe=timeframe)
        
        result = {}
        for keyword in keywords:
            result[keyword] = []
            if df is not None and not df.empty and keyword in df.columns:
                for idx, row in df.iterrows():
                    val = row[keyword]
                    if pd.isna(val):
                        continue
                    date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx).split(' ')[0]
                    result[keyword].append({
                        "date": date_str,
                        "value": float(val)
                    })
        return result

    @retry_on_429()
    def interest_by_region(self, keyword: str, geo: str = "ES-MD") -> List[Dict[str, Any]]:
        import pandas as pd
        import trendspy
        
        client = trendspy.Trends()
        df = client.interest_by_region([keyword], geo=geo)
        
        result = []
        if df is not None and not df.empty and keyword in df.columns:
            for idx, row in df.iterrows():
                val = row[keyword]
                if pd.isna(val):
                    continue
                result.append({
                    "region": str(idx),
                    "value": float(val)
                })
        return result

class FixtureProvider:
    def __init__(self, fixtures_dir: str = None):
        if fixtures_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            fixtures_dir = os.path.join(base_dir, "tests", "fixtures", "trends")
        self.fixtures_dir = fixtures_dir

    def interest_over_time(self, keywords: List[str], geo: str, timeframe: str) -> Dict[str, List[Dict[str, Any]]]:
        file_path = os.path.join(self.fixtures_dir, "interest_over_time.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {k: v for k, v in data.items() if k in keywords}
        except FileNotFoundError:
            return {k: [] for k in keywords}

    def interest_by_region(self, keyword: str, geo: str) -> List[Dict[str, Any]]:
        file_path = os.path.join(self.fixtures_dir, "interest_by_region.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(keyword, [])
        except FileNotFoundError:
            return []

def get_provider(name: str) -> TrendsProvider:
    if name == "trendspy":
        return TrendspyProvider()
    elif name == "fixture":
        return FixtureProvider()
    else:
        raise ValueError(f"Unknown provider: {name}")
