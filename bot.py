import asyncio
import random
from typing import List

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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

JOB_KWARGS = {"misfire_grace_time": 600}  # run even if first job is a bit late

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = [
        "Бот запущен ✅",
        f"Таймфреймы: {', '.join(TIMEFRAMES)}",
        f"TOP_SYMBOLS: {TOP_SYMBOLS}",
        f"MIN_SCORE: {MIN_SCORE}",
        f"Интервал сигналов: {SIGNAL_INTERVAL_MIN}-{SIGNAL_INTERVAL_MAX} сек",
        f"CHANNEL_ID: {CHANNEL_ID or '(не задан)'}",
    ]
    await update.message.reply_text("\n".join(msg))

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"TIMEFRAMES={TIMEFRAMES}\nTOP_SYMBOLS={TOP_SYMBOLS}\nMIN_SCORE={MIN_SCORE}\n"
        f"SIGNAL_INTERVAL={SIGNAL_INTERVAL_MIN}-{SIGNAL_INTERVAL_MAX} sec\nCHANNEL_ID={CHANNEL_ID or '(не задан)'}"
    )

async def produce_and_send_signal(context: ContextTypes.DEFAULT_TYPE):
    quiet = False
    if context.job and context.job.data and isinstance(context.job.data, dict):
        quiet = bool(context.job.data.get("quiet", False))
    chat_id = context.job.chat_id if context.job else None
    try:
        symbols = top_usdt_symbols(TOP_SYMBOLS)
        candidates: List[Signal] = []
        for s in symbols:
            for tf in TIMEFRAMES:
                try:
                    raw = get_klines(s, tf, limit=300)
                    df = make_dataframe(raw)
                    sig = evaluate(df, s, tf)
                    if sig:
                        candidates.append(sig)
                except Exception:
                    continue

        best = pick_best(candidates)
        if not best:
            if chat_id and not quiet:
                await context.bot.send_message(chat_id=chat_id, text="Нет подходящих сетапов сейчас. Ищу дальше...")
            return

        if best.score < MIN_SCORE:
            if chat_id and not quiet:
                await context.bot.send_message(chat_id=chat_id, text="Сигналы есть, но ниже MIN_SCORE. Ищу дальше...")
            return

        raw = get_klines(best.symbol, best.tf, limit=300)
        df = make_dataframe(raw)
        img_path = save_signal_chart(df, best.symbol, best.tf, best.entry, best.sl, best.tp, out_dir="out")

        text = to_text(best)
        if chat_id:
            with open(img_path, "rb") as f:
                await context.bot.send_photo(chat_id=chat_id, photo=f, caption=text)
    except Exception as e:
        if chat_id and not quiet:
            await context.bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")
    finally:
        delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
        if context.job_queue:
            context.job_queue.run_once(produce_and_send_signal, when=delay, chat_id=chat_id, data={"quiet": quiet}, job_kwargs=JOB_KWARGS)

async def run_scheduler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Запускаю генерацию сигналов для этого чата...")
    delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
    if context.job_queue:
        context.job_queue.run_once(produce_and_send_signal, when=delay, chat_id=update.effective_chat.id, data={"quiet": False}, job_kwargs=JOB_KWARGS)
    else:
        await update.message.reply_text("Внимание: JobQueue не инициализирован. Установите 'python-telegram-bot[job-queue]'.")

async def run_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /run_channel <channel_id или @username>")
        return
    target = context.args[0]
    await update.message.reply_text(f"Запускаю генерацию сигналов для: {target}")
    delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
    if context.job_queue:
        context.job_queue.run_once(produce_and_send_signal, when=delay, chat_id=target, data={"quiet": True}, job_kwargs=JOB_KWARGS)
    else:
        await update.message.reply_text("Внимание: JobQueue не инициализирован. Установите 'python-telegram-bot[job-queue]'.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("config", config_cmd))
    app.add_handler(CommandHandler("run", run_scheduler))
    app.add_handler(CommandHandler("run_channel", run_channel))
    print("Bot is running. Use /start in Telegram.")

    if CHANNEL_ID and app.job_queue:
        delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
        app.job_queue.run_once(produce_and_send_signal, when=delay, chat_id=CHANNEL_ID, data={"quiet": True}, job_kwargs=JOB_KWARGS)
        print(f"Auto-post enabled for {CHANNEL_ID}")
    elif CHANNEL_ID and not app.job_queue:
        print("Внимание: JobQueue не инициализирован. Установите 'python-telegram-bot[job-queue]' чтобы работал автопост в канал.")

    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
