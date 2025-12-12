# Telegram Binance Futures Signaler (RU)

Бот анализирует USDT-фьючерсы Binance по 5m/15m/30m, считает MACD, Supertrend, ADX, Volume, RSI, выбирает лучший сетап
и публикует **1 сигнал каждые 30–60 сек** (текст + PNG-график). Поддерживает каналы.

## Быстрый старт
1) Python 3.10+
2) `.env.example` → `.env`, заполнить `TELEGRAM_BOT_TOKEN`, при необходимости `CHANNEL_ID`.
3) `pip install -r requirements.txt`
4) `python bot.py`

Команды: `/start`, `/config`, `/run`, `/run_channel <id_or_@username>`

## Примечания
- Используется JobQueue (extra-зависимость PTB)
- Добавлен `misfire_grace_time` (10 минут), чтобы не «пропускать» первый джоб при старте.
