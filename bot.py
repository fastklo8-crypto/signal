import asyncio
import random
import logging
from typing import List
from datetime import datetime

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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

JOB_KWARGS = {"misfire_grace_time": 600}  # run even if first job is a bit late

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    logger.info(f"Команда /start от пользователя {update.effective_user.id}")
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
    """Обработчик команды /ping"""
    logger.info(f"Команда /ping от пользователя {update.effective_user.id}")
    await update.message.reply_text("pong")

async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /config"""
    logger.info(f"Команда /config от пользователя {update.effective_user.id}")
    await update.message.reply_text(
        f"TIMEFRAMES={TIMEFRAMES}\nTOP_SYMBOLS={TOP_SYMBOLS}\nMIN_SCORE={MIN_SCORE}\n"
        f"SIGNAL_INTERVAL={SIGNAL_INTERVAL_MIN}-{SIGNAL_INTERVAL_MAX} sec\nCHANNEL_ID={CHANNEL_ID or '(не задан)'}"
    )

async def produce_and_send_signal(context: ContextTypes.DEFAULT_TYPE):
    """Генерация и отправка сигнала"""
    quiet = False
    chat_id = None
    job_data = {}
    
    if context.job and context.job.data and isinstance(context.job.data, dict):
        job_data = context.job.data
        quiet = bool(job_data.get("quiet", False))
        chat_id = context.job.chat_id
    
    logger.info(f"Начало генерации сигнала для chat_id={chat_id}, quiet={quiet}")
    
    try:
        symbols = top_usdt_symbols(TOP_SYMBOLS)
        logger.info(f"Получено {len(symbols)} символов для анализа")
        
        candidates: List[Signal] = []
        for s in symbols:
            for tf in TIMEFRAMES:
                try:
                    raw = get_klines(s, tf, limit=300)
                    df = make_dataframe(raw)
                    sig = evaluate(df, s, tf)
                    if sig:
                        candidates.append(sig)
                        logger.debug(f"Найден кандидат: {s} {tf} score={sig.score}")
                except Exception as e:
                    logger.warning(f"Ошибка при анализе {s} на таймфрейме {tf}: {e}")
                    continue

        logger.info(f"Всего найдено кандидатов: {len(candidates)}")
        
        best = pick_best(candidates)
        if not best:
            logger.info("Нет подходящих сетапов сейчас")
            if chat_id and not quiet:
                await context.bot.send_message(chat_id=chat_id, text="Нет подходящих сетапов сейчас. Ищу дальше...")
            return

        logger.info(f"Лучший сигнал: {best.symbol} {best.tf} score={best.score}")
        
        if best.score < MIN_SCORE:
            logger.info(f"Сигнал ниже MIN_SCORE ({MIN_SCORE}): score={best.score}")
            if chat_id and not quiet:
                await context.bot.send_message(chat_id=chat_id, text="Сигналы есть, но ниже MIN_SCORE. Ищу дальше...")
            return

        # Получаем данные для построения графика
        raw = get_klines(best.symbol, best.tf, limit=300)
        df = make_dataframe(raw)
        img_path = save_signal_chart(df, best.symbol, best.tf, best.entry, best.sl, best.tp, out_dir="out")
        logger.info(f"График сохранен: {img_path}")

        text = to_text(best)
        logger.info(f"Подготовлен текст сигнала: {best.symbol} {best.tf}")
        
        if chat_id:
            try:
                with open(img_path, "rb") as f:
                    await context.bot.send_photo(chat_id=chat_id, photo=f, caption=text)
                logger.info(f"Сигнал отправлен в chat_id={chat_id}")
            except Exception as send_error:
                logger.error(f"Ошибка при отправке сигнала в chat_id={chat_id}: {send_error}")
                
    except Exception as e:
        logger.error(f"Критическая ошибка в produce_and_send_signal: {e}", exc_info=True)
        if chat_id and not quiet:
            await context.bot.send_message(chat_id=chat_id, text=f"Ошибка: {e}")
    finally:
        delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
        logger.info(f"Следующая проверка через {delay} секунд")
        if context.job_queue:
            context.job_queue.run_once(produce_and_send_signal, when=delay, chat_id=chat_id, data={"quiet": quiet}, job_kwargs=JOB_KWARGS)

async def run_scheduler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск генерации сигналов для текущего чата"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    logger.info(f"Команда /run от пользователя {user_id}, чат {chat_id}")
    
    await update.message.reply_text("Запускаю генерацию сигналов для этого чата...")
    delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
    
    if context.job_queue:
        context.job_queue.run_once(produce_and_send_signal, when=delay, chat_id=chat_id, data={"quiet": False}, job_kwargs=JOB_KWARGS)
        logger.info(f"Запланирована генерация сигналов для chat_id={chat_id} через {delay} сек")
    else:
        logger.error("JobQueue не инициализирован")
        await update.message.reply_text("Внимание: JobQueue не инициализирован. Установите 'python-telegram-bot[job-queue]'.")

async def run_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск генерации сигналов для канала"""
    user_id = update.effective_user.id
    logger.info(f"Команда /run_channel от пользователя {user_id}")
    
    if not context.args:
        logger.warning(f"Пользователь {user_id} использовал /run_channel без аргументов")
        await update.message.reply_text("Использование: /run_channel <channel_id или @username>")
        return
    
    target = context.args[0]
    logger.info(f"Запуск генерации сигналов для канала: {target}")
    
    await update.message.reply_text(f"Запускаю генерацию сигналов для: {target}")
    delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
    
    if context.job_queue:
        context.job_queue.run_once(produce_and_send_signal, when=delay, chat_id=target, data={"quiet": True}, job_kwargs=JOB_KWARGS)
        logger.info(f"Запланирована генерация сигналов для канала {target} через {delay} сек")
    else:
        logger.error("JobQueue не инициализирован")
        await update.message.reply_text("Внимание: JobQueue не инициализирован. Установите 'python-telegram-bot[job-queue]'.")

def main():
    """Основная функция запуска бота"""
    logger.info("=" * 50)
    logger.info("Запуск бота сигналов")
    logger.info(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Конфигурация: TOP_SYMBOLS={TOP_SYMBOLS}, TIMEFRAMES={TIMEFRAMES}, MIN_SCORE={MIN_SCORE}")
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("config", config_cmd))
    app.add_handler(CommandHandler("run", run_scheduler))
    app.add_handler(CommandHandler("run_channel", run_channel))
    
    logger.info("Обработчики команд зарегистрированы")
    logger.info("Bot is running. Use /start in Telegram.")

    if CHANNEL_ID and app.job_queue:
        delay = random.randint(SIGNAL_INTERVAL_MIN, SIGNAL_INTERVAL_MAX)
        app.job_queue.run_once(produce_and_send_signal, when=delay, chat_id=CHANNEL_ID, data={"quiet": True}, job_kwargs=JOB_KWARGS)
        logger.info(f"Автопостинг включен для канала {CHANNEL_ID}, первая проверка через {delay} сек")
    elif CHANNEL_ID and not app.job_queue:
        logger.warning("JobQueue не инициализирован. Установите 'python-telegram-bot[job-queue]' чтобы работал автопост в канал.")

    try:
        app.run_polling(close_loop=False)
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
    finally:
        logger.info("Бот остановлен")

if __name__ == "__main__":
    main()