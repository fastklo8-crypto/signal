import numpy as np
import pandas as pd

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def macd(close: pd.Series, fast=12, slow=26, signal=9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def rsi(close: pd.Series, period: int = 14):
    delta = close.diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up, index=close.index).ewm(alpha=1/period, adjust=False).mean()
    roll_down = pd.Series(down, index=close.index).ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-9)
    return 100 - (100 / (1 + rs))

def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(df).rolling(window=period, min_periods=period).mean()

def adx(df: pd.DataFrame, period: int = 14):
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr = true_range(df)
    atr_series = tr.rolling(window=period, min_periods=period).mean()

    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / (atr_series + 1e-9)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / (atr_series + 1e-9)

    dx = ( (plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-9) ) * 100
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx, plus_di, minus_di

def supertrend(df: pd.DataFrame, atr_period: int = 10, multiplier: float = 3.0):
    hl2 = (df["high"] + df["low"]) / 2.0
    atr_series = atr(df, period=atr_period)
    upperband = hl2 + multiplier * atr_series
    lowerband = hl2 - multiplier * atr_series

    final_ub = upperband.copy()
    final_lb = lowerband.copy()

    for i in range(1, len(df)):
        if df["close"].iloc[i-1] <= final_ub.iloc[i-1]:
            final_ub.iloc[i] = min(upperband.iloc[i], final_ub.iloc[i-1])
        else:
            final_ub.iloc[i] = upperband.iloc[i]

        if df["close"].iloc[i-1] >= final_lb.iloc[i-1]:
            final_lb.iloc[i] = max(lowerband.iloc[i], final_lb.iloc[i-1])
        else:
            final_lb.iloc[i] = lowerband.iloc[i]

    st = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)

    for i in range(len(df)):
        if i == 0:
            st.iloc[i] = float("nan")
            direction.iloc[i] = 0
        else:
            if df["close"].iloc[i] > final_ub.iloc[i-1]:
                direction.iloc[i] = 1
            elif df["close"].iloc[i] < final_lb.iloc[i-1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i-1]

            st.iloc[i] = final_lb.iloc[i] if direction.iloc[i] == 1 else final_ub.iloc[i]

    return st, direction, atr_series
