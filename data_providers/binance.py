import time
import requests
from typing import List, Dict, Any, Optional

from config import BINANCE_API_BASE

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "tg-futures-signal-bot/1.0"})

def _get(url: str, params: Optional[dict] = None, retries: int = 3, timeout: int = 10):
    last_exc = None
    for _ in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            time.sleep(0.2)
        except Exception as e:
            last_exc = e
            time.sleep(0.5)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"GET {url} failed")

def get_futures_exchange_info() -> Dict[str, Any]:
    url = f"{BINANCE_API_BASE}/fapi/v1/exchangeInfo"
    return _get(url)

def get_24h_tickers() -> List[Dict[str, Any]]:
    url = f"{BINANCE_API_BASE}/fapi/v1/ticker/24hr"
    return _get(url)

def get_klines(symbol: str, interval: str, limit: int = 300) -> List[List[Any]]:
    url = f"{BINANCE_API_BASE}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    return _get(url, params=params)

def top_usdt_symbols(limit: int = 40) -> List[str]:
    info = get_futures_exchange_info()
    symbols_ok = {s["symbol"] for s in info["symbols"] if s.get("status") == "TRADING" and s["quoteAsset"] == "USDT"}
    tickers = get_24h_tickers()
    rows = []
    for t in tickers:
        s = t.get("symbol")
        if s in symbols_ok and s.endswith("USDT"):
            try:
                qv = float(t.get("quoteVolume", 0.0))
                rows.append((s, qv))
            except:
                pass
    rows.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in rows[:limit]]
