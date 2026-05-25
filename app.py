import os
import threading
import time
from datetime import datetime
from flask import Flask, request
import requests

app = Flask(__name__)

TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
ALLOWED_IDS_RAW = os.environ.get('ALLOWED_IDS', 'd1_m__h')
ALLOWED_IDS = [id.strip() for id in ALLOWED_IDS_RAW.split(',')]

TIMEOUT_SEC = 600  # 10 минут

# Хранилище устройств
devices = {}

# Блокировка для потокобезопасности
from threading import Lock
devices_lock = Lock()

def send_telegram_alert(device_id):
    """Отправляет сообщение о пропаже интернета (ТОЛЬКО ОДИН РАЗ)"""
    with devices_lock:
        if device_id not in devices:
            print(f"[ALERT] Device {device_id} not found")
            return
        
        # ЕСЛИ УЖЕ ОТПРАВЛЕНО — ВЫХОДИМ
        if devices[device_id].get('alert_sent', False):
            print(f"[ALERT] Alert already sent for {device_id}, skipping")
            return
        
        print(f"[ALERT] Sending alert for {device_id}")
        # Помечаем, что отправляем
        devices[device_id]['alert_sent'] = True
    
    if TOKEN and CHAT_ID:
        try:
            url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
            message = f'❌ ПРОПАЛ ИНТЕРНЕТ: {device_id} (нет пингов более {TIMEOUT_SEC // 60} минут)'
            response = requests.post(url, json={
                'chat_id': CHAT_ID,
                'text': message
            }, timeout=5)
            print(f"[ALERT] Response: {response.status_code}")
        except Exception as e:
            print(f"[ALERT] Error sending: {e}")
            # Если отправка не удалась, сбрасываем флаг
            with devices_lock:
                if device_id in devices:
                    devices[device_id]['alert_sent'] = False

def check_device_timeout(device_id):
    """Функция для таймера — проверяет, нужно ли отправить alert"""
    with devices_lock:
        if device_id not in devices:
            return
        
        last_seen = devices[device_id].get('last_seen', 0)
        alert_sent = devices[device_id].get('alert_sent', False)
        now = time.time()
        
        print(f"[TIMER] Device {device_id}: last_seen={last_seen}, now={now}, diff={now - last_seen}, alert_sent={alert_sent}")
        
        # Если прошло больше TIMEOUT_SEC и alert ещё не отправлен
        if not alert_sent and (now - last_seen) > TIMEOUT_SEC:
            # Отправляем alert (снимаем блокировку внутри функции)
            send_telegram_alert(device_id)

def start_timer(device_id):
    """Запускает таймер для устройства"""
    timer = threading.Timer(TIMEOUT_SEC, check_device_timeout, args=[device_id])
    timer.daemon = True
    return timer

@app.route('/')
def home():
    return 'Internet Monitor Running'

@app.route('/ping')
def ping():
    """Принимает пинги от устройств"""
    device_id = request.args.get('id', 'unknown')
    
    print(f"[PING] Received from {device_id}")
    
    # Проверка разрешенных устройств
    if device_id not in ALLOWED_IDS:
        print(f"[PING] Forbidden: {device_id}")
        return f"Forbidden: {device_id} not allowed", 403
    
    now = time.time()
    
    with devices_lock:
        # Создаем или обновляем запись
        if device_id not in devices:
            devices[device_id] = {
                'last_seen': now,
                'alert_sent': False,
                'timer': None
            }
            print(f"[PING] New device: {device_id}")
        else:
            devices[device_id]['last_seen'] = now
            devices[device_id]['alert_sent'] = False  # СБРАСЫВАЕМ ФЛАГ ПРИ ПИНГЕ
            print(f"[PING] Reset alert_sent for {device_id}")
        
        # Останавливаем старый таймер
        old_timer = devices[device_id]['timer']
        if old_timer and old_timer.is_alive():
            old_timer.cancel()
            print(f"[PING] Cancelled old timer for {device_id}")
        
        # Запускаем новый таймер
        devices[device_id]['timer'] = start_timer(device_id)
        devices[device_id]['timer'].start()
        print(f"[PING] Started new timer for {device_id}")
    
    return f"OK: {device_id}"

@app.route('/status')
def status():
    """Возвращает статус всех устройств"""
    with devices_lock:
        result = {}
        for device_id, data in devices.items():
            last_seen_str = datetime.fromtimestamp(data['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
            result[device_id] = {
                'last_ping': last_seen_str,
                'alert_sent': data.get('alert_sent', False),
                'time_since_last': int(time.time() - data['last_seen'])
            }
    return result

@app.route('/debug')
def debug():
    """Отладочный эндпоинт (можно удалить позже)"""
    with devices_lock:
        return {
            'devices': list(devices.keys()),
            'allowed_ids': ALLOWED_IDS,
            'timeout_sec': TIMEOUT_SEC
        }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
