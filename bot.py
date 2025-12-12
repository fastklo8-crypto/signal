import random
import logging
from typing import List

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    TOP_SYMBOLS,
    TIMEFRAMES,
    MIN_SCORE,
    SIGNAL_INTERVAL_MIN,
    SIGNAL_INTERVAL_MAX,
    CHANNEL_ID,
)

from data_providers.binance import top_usdt_symbols, get_klines
from analyzer import make_dataframe, evaluate, pick_best, Signal
from signal_formatter import to_text
from chart import save_signal_chart


# -------------------- logging --------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

JOB_KWARGS = {"misfire_grace_time": 600}
_last_coin = None


# -------------------- core logic --------------------

async def produce_and_send_signal(context: ContextTypes.DEFAULT_TYPE):
    global _last_coin

    quiet = False
    if context.job and isinstance(context.job.data, dict):
        quiet = context.job.data.get("quiet", False)

    chat_id = context.job.chat_id if context.job else None

    try:
        symbols = top_usdt_symbols(TOP_SYMBOLS)
        candidates: List[Signal] = []

        for symbol in symbols:
            for tf in TIMEFRAMES:
                try:
                    raw = get_klines(symbol, tf, limit=300)
                    df = make_dataframe(raw)
                    sig = evaluate(df, symbol, tf)
                    if sig:
                        candidates.append(sig)
                except Exception as e:
                    logger.warning(f"Ошибка {symbol} {tf}: {e}")

        candidates = [c for c in candidates if c.symbol != _last_coin]

        if not candidates:
            if chat_id and not quiet:
                await context.bot.send_message(chat_id, "Нет новых сигналов. Жду…")
            return

        best = pick_best(candidates)

        if not best or best.score < MIN_SCORE:
            if chat_id and not quiet:
                await context.bot.send_message(chat_id, "Нет сигналов выше MIN_SCORE.")
            return

        _last_coin = best.symbol

        raw = get_klines(best.symbol, best.tf, limit=300)
        df = make_dataframe(raw)

        img_path = save_signal_chart(
            df,
            best.symbol,
            best.tf,
            best.entry,
            best.sl,
            best.tp,
            out_dir="out",
        )

        text = to_text(best)

        if chat_id:
            try:
                with open(img_path, "rb") as f:
                    await context.bot.send_photo(chat_id, photo=f, caption=text)
            except Exception:
                await context.bot.send_message(chat_id, text)

    except Exception as e:
        logger.exception("Ошибка в produce_and_send_signal")
        if chat_id and not quiet:
            await context.bot.send_message(chat_id, f"Ошибка: {e}")

    finally:
        delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
        if context.job_queue and chat_id:
            context.job_queue.run_once(
                produce_and_send_signal,
                when=delay,
                chat_id=chat_id,
                data={"quiet": quiet},
                job_kwargs=JOB_KWARGS,
            )


# -------------------- commands --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот запущен ✅\n"
        f"TIMEFRAMES: {TIMEFRAMES}\n"
        f"TOP_SYMBOLS: {TOP_SYMBOLS}\n"
        f"MIN_SCORE: {MIN_SCORE}\n"
        f"INTERVAL: {SIGNAL_INTERVAL_MIN}-{SIGNAL_INTERVAL_MAX} сек"
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong ✅")


async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Запускаю генерацию сигналов…")
    delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)

    if context.job_queue:
        context.job_queue.run_once(
            produce_and_send_signal,
            when=delay,
            chat_id=update.effective_chat.id,
            data={"quiet": False},
            job_kwargs=JOB_KWARGS,
        )


async def run_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /run_channel <channel_id>")
        return

    target = context.args[0]
    delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)

    if context.job_queue:
        context.job_queue.run_once(
            produce_and_send_signal,
            when=delay,
            chat_id=target,
            data={"quiet": True},
            job_kwargs=JOB_KWARGS,
        )

    await update.message.reply_text(f"Автопост запущен для {target}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled error", exc_info=context.error)


# -------------------- main --------------------

def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("run", run_cmd))
    application.add_handler(CommandHandler("run_channel", run_channel))
    application.add_error_handler(error_handler)

    if CHANNEL_ID and application.job_queue:
        delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
        application.job_queue.run_once(
            produce_and_send_signal,
            when=delay,
            chat_id=CHANNEL_ID,
            data={"quiet": True},
            job_kwargs=JOB_KWARGS,
        )
        logger.info(f"Auto-post enabled for {CHANNEL_ID}")

    application.run_polling()


if __name__ == "__main__":
    main()
