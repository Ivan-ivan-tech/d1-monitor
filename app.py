from flask import Flask, request
from datetime import datetime
import requests
import threading
import os

app = Flask(__name__)

TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
TIMEOUT_SEC = 600

devices = {}

def send_alert(device_id):
    if device_id in devices and not devices[device_id]['alert_sent']:
        devices[device_id]['alert_sent'] = True
        if TOKEN and CHAT_ID:
            url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
            msg = f'❌ ПРОПАЛ ИНТЕРНЕТ: {device_id}'
            try:
                requests.post(url, json={'chat_id': CHAT_ID, 'text': msg}, timeout=5)
            except:
                pass

@app.route('/ping')
def ping():
    device_id = request.args.get('id', 'unknown')
    now = datetime.now().timestamp()
    
    if device_id not in devices:
        devices[device_id] = {'last_seen': now, 'alert_sent': False, 'timer': None}
    
    if devices[device_id]['timer'] and devices[device_id]['timer'].is_alive():
        devices[device_id]['timer'].cancel()
    
    devices[device_id]['alert_sent'] = False
    devices[device_id]['last_seen'] = now
    
    timer = threading.Timer(TIMEOUT_SEC, send_alert, args=[device_id])
    timer.daemon = True
    devices[device_id]['timer'] = timer
    timer.start()
    
    return f'OK: {device_id}'

@app.route('/status')
def status():
    result = {}
    for device_id, data in devices.items():
        last = datetime.fromtimestamp(data['last_seen']).strftime('%H:%M:%S')
        result[device_id] = last
    return result

@app.route('/')
def home():
    return 'Server running. Use /ping'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
