from flask import Flask
import threading
import time

# Создаем минимальное Flask приложение для keep-alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is alive!"

def run():
    """Запускает Flask сервер в отдельном потоке"""
    flask_app.run(host='0.0.0.0', port=8080)

# Глобальная переменная для доступа к приложению
app = flask_app

# Функция для запуска в потоке (если нужно)
def start_keep_alive():
    """Запускает keep-alive сервер в отдельном потоке"""
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
    return thread