import time
import random
import requests
from typing import List, Dict, Any, Optional, Tuple

from config import BINANCE_API_BASE

# Futures and Spot base URLs
FUTURES_BASE = "https://fapi.binance.com"
SPOT_BASE = "https://api.binance.com"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "tg-signal-bot/1.1"})


def _is_futures_base(base: str) -> bool:
    b = (base or "").lower()
    return "fapi.binance.com" in b or b.rstrip("/").endswith("/fapi") or "/fapi" in b


def _get(
    url: str,
    params: Optional[dict] = None,
    retries: int = 5,
    timeout: int = 12,
    backoff_base: float = 0.6,
) -> Any:
    """GET with retries + exponential backoff.

    Raises RuntimeError with details (status code, url) on final failure.
    """
    last_exc: Optional[BaseException] = None
    last_status: Optional[int] = None
    last_text: str = ""

    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            last_status = r.status_code

            # Success
            if r.status_code == 200:
                return r.json()

            # Binance rate-limit / ban codes
            last_text = (r.text or "")[:500]
            if r.status_code in (418, 429):
                # Longer backoff for rate limits
                sleep_s = min(30.0, backoff_base * (2 ** (attempt - 1)) + random.random())
                time.sleep(sleep_s)
                continue

            # Other HTTP errors: short backoff then retry
            sleep_s = min(10.0, backoff_base * (2 ** (attempt - 1)) + random.random() * 0.5)
            time.sleep(sleep_s)
            continue

        except Exception as e:
            last_exc = e
            sleep_s = min(10.0, backoff_base * (2 ** (attempt - 1)) + random.random() * 0.5)
            time.sleep(sleep_s)

    detail = f"GET {url} failed"
    if last_status is not None:
        detail += f" (status={last_status})"
    if last_text:
        detail += f" body={last_text!r}"
    if last_exc:
        detail += f" exc={last_exc!r}"
    raise RuntimeError(detail)


def _endpoints(base: str) -> Tuple[str, str, str]:
    """Return (exchangeInfo, ticker24hr, klines) endpoints for base."""
    b = base.rstrip("/")
    if _is_futures_base(base):
        return (
            f"{b}/fapi/v1/exchangeInfo",
            f"{b}/fapi/v1/ticker/24hr",
            f"{b}/fapi/v1/klines",
        )
    return (
        f"{b}/api/v3/exchangeInfo",
        f"{b}/api/v3/ticker/24hr",
        f"{b}/api/v3/klines",
    )


def _get_with_fallback(
    primary_base: str,
    params: Optional[dict],
    which: str,
) -> Any:
    """Try primary base; if it's futures and fails, fallback to spot."""
    ex_url, t24_url, k_url = _endpoints(primary_base)
    url = {"exchangeInfo": ex_url, "ticker24hr": t24_url, "klines": k_url}[which]

    try:
        return _get(url, params=params)
    except Exception:
        # Fallback futures->spot (common on cloud IPs)
        if _is_futures_base(primary_base):
            ex2, t242, k2 = _endpoints(SPOT_BASE)
            url2 = {"exchangeInfo": ex2, "ticker24hr": t242, "klines": k2}[which]
            return _get(url2, params=params)
        raise


def get_exchange_info() -> Dict[str, Any]:
    return _get_with_fallback(BINANCE_API_BASE, params=None, which="exchangeInfo")


def get_24h_tickers() -> List[Dict[str, Any]]:
    return _get_with_fallback(BINANCE_API_BASE, params=None, which="ticker24hr")


def get_klines(symbol: str, interval: str, limit: int = 300) -> List[List[Any]]:
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    return _get_with_fallback(BINANCE_API_BASE, params=params, which="klines")


def top_usdt_symbols(limit: int = 40) -> List[str]:
    info = get_exchange_info()

    # exchangeInfo schema is compatible for our needs across spot & futures
    symbols_ok = {
        s["symbol"]
        for s in info.get("symbols", [])
        if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"
    }

    tickers = get_24h_tickers()
    rows = []
    for t in tickers:
        s = t.get("symbol")
        if s in symbols_ok and s.endswith("USDT"):
            try:
                qv = float(t.get("quoteVolume", 0.0))
                rows.append((s, qv))
            except Exception:
                pass

    rows.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in rows[:limit]]
