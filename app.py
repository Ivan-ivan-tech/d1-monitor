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

# Хранилище: для каждого устройства запоминаем время последнего пинга и отправляли ли тревогу
devices = {}

def send_telegram_alert(device_id):
    """Отправляет сообщение ТОЛЬКО ОДИН РАЗ за пропадание"""
    # Если устройства нет в словаре — выходим
    if device_id not in devices:
        return
    
    # Если уже отправляли — выходим
    if devices[device_id].get('alert_sent', False):
        print(f"[ALERT] Уже отправлено для {device_id}, пропускаем")
        return
    
    # Отправляем
    if TOKEN and CHAT_ID:
        try:
            url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
            message = f'❌ ПРОПАЛ ИНТЕРНЕТ: {device_id} (нет пингов более {TIMEOUT_SEC // 60} минут)'
            requests.post(url, json={'chat_id': CHAT_ID, 'text': message}, timeout=5)
            print(f"[ALERT] Отправлено для {device_id}")
            
            # ПОСЛЕ УСПЕШНОЙ ОТПРАВКИ — СТАВИМ ФЛАГ
            devices[device_id]['alert_sent'] = True
        except Exception as e:
            print(f"[ALERT] Ошибка: {e}")

@app.route('/')
def home():
    return 'Internet Monitor Running'

@app.route('/ping')
def ping():
    device_id = request.args.get('id', 'unknown')
    
    if device_id not in ALLOWED_IDS:
        return f"Forbidden: {device_id}", 403
    
    now = time.time()
    
    # Создаём запись, если её нет
    if device_id not in devices:
        devices[device_id] = {
            'last_seen': now,
            'alert_sent': False,
            'timer': None
        }
    
    # Обновляем время последнего пинга
    devices[device_id]['last_seen'] = now
    
    # Если был флаг тревоги — сбрасываем (интернет вернулся)
    if devices[device_id].get('alert_sent', False):
        print(f"[PING] {device_id} вернулся, сбрасываем alert_sent")
        devices[device_id]['alert_sent'] = False
    
    # Останавливаем старый таймер, если есть
    old_timer = devices[device_id].get('timer')
    if old_timer and old_timer.is_alive():
        old_timer.cancel()
        print(f"[PING] Остановлен старый таймер для {device_id}")
    
    # Запускаем новый таймер
    timer = threading.Timer(TIMEOUT_SEC, send_telegram_alert, args=[device_id])
    timer.daemon = True
    devices[device_id]['timer'] = timer
    timer.start()
    
    print(f"[PING] {device_id} обновлён, новый таймер на {TIMEOUT_SEC} сек")
    
    return f"OK: {device_id}"

@app.route('/status')
def status():
    result = {}
    now = time.time()
    for device_id, data in devices.items():
        last_seen_str = datetime.fromtimestamp(data['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
        result[device_id] = {
            'last_ping': last_seen_str,
            'alert_sent': data.get('alert_sent', False),
            'seconds_ago': int(now - data['last_seen'])
        }
    return result

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
