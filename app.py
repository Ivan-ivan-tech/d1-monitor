import os
import threading
from datetime import datetime
from flask import Flask, request
import requests

# --- 1. СОЗДАЕМ ПРИЛОЖЕНИЕ ---
app = Flask(__name__)

# --- 2. ЧИТАЕМ ПЕРЕМЕННЫЕ ---
TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# ID устройств (через запятую)
ALLOWED_IDS_RAW = os.environ.get('ALLOWED_IDS', 'd1_m__h')
ALLOWED_IDS = [id.strip() for id in ALLOWED_IDS_RAW.split(',')]

TIMEOUT_SEC = 600  # 10 минут

# Хранилище устройств
devices = {}

# --- 3. ФУНКЦИИ ПОМОЩНИКИ ---
def send_telegram_alert(device_id):
    """Отправляет сообщение о пропаже интернета (ТОЛЬКО ОДИН РАЗ)"""
    if device_id not in devices:
        return
    
    # ЕСЛИ УЖЕ ОТПРАВЛЕНО — ВЫХОДИМ
    if devices[device_id].get('alert_sent', False):
        print(f"Alert already sent for {device_id}, skipping")
        return
    
    # Помечаем, что отправляем
    devices[device_id]['alert_sent'] = True
    
    if TOKEN and CHAT_ID:
        try:
            url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
            message = f'❌ ПРОПАЛ ИНТЕРНЕТ: {device_id} (нет пингов более {TIMEOUT_SEC // 60} минут)'
            requests.post(url, json={
                'chat_id': CHAT_ID,
                'text': message
            }, timeout=5)
            print(f"Alert sent for {device_id} at {datetime.now()}")
        except Exception as e:
            print(f"Ошибка отправки Telegram: {e}")
            # Если отправка не удалась, сбрасываем флаг для повторной попытки
            devices[device_id]['alert_sent'] = False

# --- 4. ФОНТОВАЯ ЗАДАЧА ДЛЯ ПЕРИОДИЧЕСКОЙ ПРОВЕРКИ (ЗАПАСНОЙ ВАРИАНТ) ---
def check_all_devices():
    """Периодически проверяет все устройства и отправляет alert если нужно"""
    now = datetime.now().timestamp()
    
    for device_id, data in devices.items():
        last_seen = data.get('last_seen', 0)
        alert_sent = data.get('alert_sent', False)
        
        # Если прошло больше TIMEOUT_SEC и alert ещё не отправлен
        if not alert_sent and (now - last_seen) > TIMEOUT_SEC:
            print(f"Periodic check: device {device_id} timed out")
            send_telegram_alert(device_id)
    
    # Запускаем снова через 60 секунд
    threading.Timer(60, check_all_devices).start()

# --- 5. ЭНДПОИНТЫ ---
@app.route('/')
def home():
    return 'Internet Monitor Running'

@app.route('/ping')
def ping():
    """Принимает пинги от устройств"""
    device_id = request.args.get('id', 'unknown')
    
    # Проверка разрешенных устройств
    if device_id not in ALLOWED_IDS:
        return f"Forbidden: {device_id} not allowed", 403
    
    now = datetime.now().timestamp()
    
    # Создаем или обновляем запись
    if device_id not in devices:
        devices[device_id] = {
            'last_seen': now,
            'alert_sent': False
        }
    else:
        devices[device_id]['last_seen'] = now
        devices[device_id]['alert_sent'] = False  # СБРАСЫВАЕМ ФЛАГ ПРИ ПИНГЕ
        print(f"Ping from {device_id}, alert_sent reset to False")
    
    return f"OK: {device_id}"

@app.route('/status')
def status():
    """Возвращает статус всех устройств"""
    result = {}
    for device_id, data in devices.items():
        last_seen_str = datetime.fromtimestamp(data['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
        result[device_id] = {
            'last_ping': last_seen_str,
            'alert_sent': data.get('alert_sent', False),
            'status': 'ALERT SENT' if data.get('alert_sent') else 'OK'
        }
    return result

# --- 6. ЗАПУСК ---
if __name__ == '__main__':
    # Запускаем фоновую проверку
    threading.Timer(60, check_all_devices).start()
    app.run(host='0.0.0.0', port=10000)
