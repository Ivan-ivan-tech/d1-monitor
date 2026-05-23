"""
Сервер для мониторинга интернета D1 mini
Принимает пинги от ESP8266, отправляет Telegram при пропадании связи
"""

import os
from flask import Flask, request
from datetime import datetime
import requests
import threading

app = Flask(__name__)

# ================= НАСТРОЙКИ =================
TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Разрешённые устройства (читаем из переменной окружения)
# Можно указать несколько ID через запятую: "id1,id2,id3"
ALLOWED_IDS_RAW = os.environ.get('ALLOWED_IDS', 'd1_m__h')
ALLOWED_IDS = [id.strip() for id in ALLOWED_IDS_RAW.split(',')]

TIMEOUT_SEC = 600  # 10 минут без пинга → тревога

# Хранилище устройств
devices = {}


def send_telegram_alert(device_id):
    """Отправляет сообщение о пропаже интернета"""
    if TOKEN and CHAT_ID:
        try:
            url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
            message = f'❌ ПРОПАЛ ИНТЕРНЕТ: {device_id} (нет пингов более {TIMEOUT_SEC // 60} минут)'
            response = requests.post(url, json={
                'chat_id': CHAT_ID,
                'text': message
            }, timeout=5)
            print(f"Alert sent: {response.status_code}")
        except Exception as e:
            print(f"Ошибка отправки Telegram: {e}")


@app.route('/ping')
def ping():
    """Эндпоинт для пингов от устройств"""
    device_id = request.args.get('id', 'unknown')
    
    # --- ПРОВЕРКА РАЗРЕШЁННЫХ УСТРОЙСТВ ---
    if device_id not in ALLOWED_IDS:
        return f"Forbidden: {device_id} not allowed", 403
    # ---
    
    now = datetime.now().timestamp()
    
    # Если устройство новое — создаём запись
    if device_id not in devices:
        devices[device_id] = {
            'last_seen': now,
            'alert_sent': False,
            'timer': None
        }
    
    # Останавливаем предыдущий таймер, если был
    if devices[device_id]['timer'] and devices[device_id]['timer'].is_alive():
        devices[device_id]['timer'].cancel()
    
    # Сбрасываем флаг тревоги
    devices[device_id]['alert_sent'] = False
    devices[device_id]['last_seen'] = now
    
    # Запускаем новый таймер: через TIMEOUT_SEC отправить предупреждение
    timer = threading.Timer(TIMEOUT_SEC, send_telegram_alert, args=[device_id])
    timer.daemon = True
    devices[device_id]['timer'] = timer
    timer.start()
    
    return f"OK: {device_id}"


@app.route('/status')
def status():
    """Возвращает статус всех устройств (последний пинг)"""
    result = {}
    for device_id, data in devices.items():
        last_seen = datetime.fromtimestamp(data['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
        alert_status = "ALERT SENT" if data['alert_sent'] else "OK"
        result[device_id] = {
            'last_ping': last_seen,
            'status': alert_status
        }
    return result


@app.route('/reset/<device_id>')
def reset(device_id):
    """Принудительный сброс статуса устройства (для отладки)"""
    if device_id in devices:
        if devices[device_id]['timer'] and devices[device_id]['timer'].is_alive():
            devices[device_id]['timer'].cancel()
        del devices[device_id]
        return f"Reset: {device_id}"
    return f"Device not found: {device_id}"


@app.route('/')
def home():
    """Домашняя страница"""
    return f'Server running. Allowed devices: {ALLOWED_IDS}'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
