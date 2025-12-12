from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
from datetime import datetime, timezone

from indicators import macd, rsi, adx, supertrend
from config import ATR_SL_MULT, ATR_TP_MULT, BUDGET_USDT

@dataclass
class Signal:
    symbol: str
    tf: str
    side: str  # LONG / SHORT
    entry: float
    sl: float
    tp: float
    score: int
    reasons: list
    strength: str
    rec_usd: float
    timestamp_utc: str

def _strength(score: int) -> str:
    if score >= 4:
        return "Сильный"
    if score >= 2:
        return "Средний"
    return "Слабый"

def _recommend_amount(score: int, budget: float = BUDGET_USDT) -> float:
    base = {0: 0.03, 1: 0.05, 2: 0.08, 3: 0.10, 4: 0.12, 5: 0.15}.get(score, 0.12)
    return round(max(5.0, min(budget * base, budget * 0.2)), 2)

def make_dataframe(klines):
    cols = ["open_time","open","high","low","close","volume","close_time",
            "qav","trades","tbbav","tbqav","ignore"]
    df = pd.DataFrame(klines, columns=cols)
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[["open","high","low","close","volume"]].copy()

def evaluate(df: pd.DataFrame, symbol: str, tf: str) -> Optional[Signal]:
    if len(df) < 100 or df["close"].isna().sum() > 0:
        return None

    macd_line, signal_line, macd_hist = macd(df["close"])
    rsi14 = rsi(df["close"])
    adx14, plus_di, minus_di = adx(df)
    st, st_dir, atr_series = supertrend(df)

    vol_sma20 = df["volume"].rolling(20).mean()
    vol_spike = (df["volume"] / (vol_sma20 + 1e-9)).iloc[-1]

    long_points = 0
    short_points = 0
    reasons_long = []
    reasons_short = []

    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        long_points += 1; reasons_long.append("MACD>signal")
    else:
        short_points += 1; reasons_short.append("MACD<signal")

    if rsi14.iloc[-1] < 35:
        long_points += 1; reasons_long.append("RSI<35")
    if rsi14.iloc[-1] > 65:
        short_points += 1; reasons_short.append("RSI>65")

    if st_dir.iloc[-1] == 1:
        long_points += 1; reasons_long.append("ST up")
    elif st_dir.iloc[-1] == -1:
        short_points += 1; reasons_short.append("ST down")

    if adx14.iloc[-1] > 20:
        if plus_di.iloc[-1] > minus_di.iloc[-1]:
            long_points += 1; reasons_long.append("ADX>20 & +DI")
        else:
            short_points += 1; reasons_short.append("ADX>20 & -DI")

    if vol_spike >= 1.5:
        if long_points >= short_points:
            long_points += 1; reasons_long.append(f"{vol_spike:.1f}x vol")
        else:
            short_points += 1; reasons_short.append(f"{vol_spike:.1f}x vol")

    side = "LONG" if long_points >= short_points else "SHORT"
    score = max(long_points, short_points)

    last_close = float(df["close"].iloc[-1])
    atr14 = float(atr_series.iloc[-1])

    if side == "LONG":
        entry = last_close
        sl = max(1e-12, entry - ATR_SL_MULT * atr14)
        tp = entry + ATR_TP_MULT * atr14
        reasons = reasons_long
    else:
        entry = last_close
        sl = entry + ATR_SL_MULT * atr14
        tp = max(1e-12, entry - ATR_TP_MULT * atr14)
        reasons = reasons_short

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    strength = _strength(score)
    rec = _recommend_amount(score)

    return Signal(
        symbol=symbol,
        tf=tf,
        side=side,
        entry=round(entry, 8),
        sl=round(sl, 8),
        tp=round(tp, 8),
        score=int(score),
        reasons=reasons,
        strength=strength,
        rec_usd=rec,
        timestamp_utc=stamp,
    )

def pick_best(candidates: List[Signal]):
    if not candidates:
        return None
    tf_weight = {"15m": 2, "5m": 1, "30m": 1}
    def key(s: Signal):
        spike = any("x vol" in r for r in s.reasons)
        return (s.score, 1 if spike else 0, tf_weight.get(s.tf, 0))
    return sorted(candidates, key=key, reverse=True)[0]
