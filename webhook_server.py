import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаем Flask приложение
app = Flask(__name__)

# Будем получать application из bot.py
try:
    from bot import application
    if application is None:
        raise ImportError("Application not initialized in bot.py")
except ImportError as e:
    logger.error(f"Failed to import application: {e}")
    application = None

@app.route('/')
def index():
    return "Telegram Bot is running! Use webhook endpoint for updates."

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Обработчик webhook от Telegram"""
    if application is None:
        return "Bot application not initialized", 500
    
    try:
        # Получаем данные от Telegram
        json_data = await request.get_json()
        update = Update.de_json(json_data, application.bot)
        
        # Обрабатываем update
        await application.process_update(update)
        
        return "OK"
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return "Error", 500

@app.route('/health', methods=['GET'])
def health():
    """Health check для Render"""
    if application and application.bot:
        return {"status": "healthy", "bot": "initialized"}, 200
    return {"status": "unhealthy", "bot": "not initialized"}, 500

async def set_webhook():
    """Установка webhook URL"""
    if application is None:
        logger.error("Application not initialized, cannot set webhook")
        return
    
    try:
        # Получаем URL из переменной окружения или используем Render URL
        webhook_url = os.environ.get('WEBHOOK_URL')
        
        if not webhook_url:
            # Для Render обычно что-то вроде https://your-app.onrender.com/webhook
            logger.warning("WEBHOOK_URL not set in environment variables")
            return
        
        # Устанавливаем webhook
        await application.bot.set_webhook(
            url=f"{webhook_url}/webhook",
            drop_pending_updates=True
        )
        logger.info(f"Webhook set to: {webhook_url}/webhook")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

if __name__ == '__main__':
    # Запускаем настройку webhook при старте
    import asyncio
    if application:
        asyncio.run(set_webhook())
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)