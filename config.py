import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

BINANCE_API_BASE = os.getenv("BINANCE_API_BASE", "https://fapi.binance.com").strip()
TOP_SYMBOLS = int(os.getenv("TOP_SYMBOLS", "40"))
TIMEFRAMES = [tf.strip() for tf in os.getenv("TIMEFRAMES", "5m,15m,30m").split(",") if tf.strip()]
MIN_SCORE = int(os.getenv("MIN_SCORE", "1"))

SIGNAL_INTERVAL_MIN = int(os.getenv("SIGNAL_INTERVAL_MIN", "30"))
SIGNAL_INTERVAL_MAX = int(os.getenv("SIGNAL_INTERVAL_MAX", "60"))

BUDGET_USDT = float(os.getenv("BUDGET_USDT", "100"))

CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()

ATR_SL_MULT = float(os.getenv("ATR_SL_MULT", "1.5"))
ATR_TP_MULT = float(os.getenv("ATR_TP_MULT", "2.0"))

assert TELEGRAM_BOT_TOKEN, "TELEGRAM_BOT_TOKEN is required"
assert SIGNAL_INTERVAL_MIN > 0 and SIGNAL_INTERVAL_MAX >= SIGNAL_INTERVAL_MIN
