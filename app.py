import os
import threading
from datetime import datetime
from flask import Flask, request
import requests

# --- 1. СОЗДАЕМ ПРИЛОЖЕНИЕ (ДО ВСЕХ @app.route) ---
app = Flask(__name__)

# --- 2. ЧИТАЕМ ПЕРЕМЕННЫЕ ---
TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# ID устройств (через запятую)
ALLOWED_IDS_RAW = os.environ.get('ALLOWED_IDS', 'd1_m__h')
ALLOWED_IDS = [id.strip() for id in ALLOWED_IDS_RAW.split(',')]

TIMEOUT_SEC = 600  # 10 минут

# Хранилище устройств (словарь)
devices = {}

# --- 3. ФУНКЦИИ ПОМОЩНИКИ ---
def send_telegram_alert(device_id):
    """Отправляет сообщение о пропаже интернета"""
    if TOKEN and CHAT_ID:
        try:
            url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
            message = f'❌ ПРОПАЛ ИНТЕРНЕТ: {device_id} (нет пингов более {TIMEOUT_SEC // 60} минут)'
            requests.post(url, json={
                'chat_id': CHAT_ID,
                'text': message
            }, timeout=5)
            print(f"Alert sent for {device_id}")
        except Exception as e:
            print(f"Ошибка отправки Telegram: {e}")

# --- 4. ЭНДПОИНТЫ (маршруты) ---
@app.route('/')
def home():
    """Главная страница — скрываем список устройств"""
    return 'Server running. Monitor active.'

@app.route('/ping')
def ping():
    """Принимает пинги от устройств"""
    device_id = request.args.get('id', 'unknown')
    
    # Проверка разрешенных устройств
    if device_id not in ALLOWED_IDS:
        return f"Forbidden: {device_id} not allowed", 403
    
    now = datetime.now().timestamp()
    
    # Создаем запись, если устройство новое
    if device_id not in devices:
        devices[device_id] = {
            'last_seen': now,
            'alert_sent': False,
            'timer': None
        }
    
    # Останавливаем старый таймер
    old_timer = devices[device_id]['timer']
    if old_timer and old_timer.is_alive():
        old_timer.cancel()
    
    # Сбрасываем флаг тревоги
    devices[device_id]['alert_sent'] = False
    devices[device_id]['last_seen'] = now
    
    # Запускаем новый таймер
    timer = threading.Timer(TIMEOUT_SEC, send_telegram_alert, args=[device_id])
    timer.daemon = True
    devices[device_id]['timer'] = timer
    timer.start()
    
    return f"OK: {device_id}"

@app.route('/status')
def status():
    """Возвращает статус всех устройств (можно закрыть ключом, если нужно)"""
    # Если хотите закрыть статус ключом, раскомментируйте эти строки:
    # api_key = request.headers.get('X-API-Key')
    # if api_key != os.environ.get('API_KEY', ''):
    #     return 'Unauthorized', 401
    
    result = {}
    for device_id, data in devices.items():
        last_seen_str = datetime.fromtimestamp(data['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
        result[device_id] = {
            'last_ping': last_seen_str,
            'status': 'ALERT SENT' if data['alert_sent'] else 'OK'
        }
    return result

# --- 5. ЗАПУСК (для локального теста) ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
