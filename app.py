@app.route('/')
def home():
    return 'Server running. Monitor active.'

@app.route('/status')
def status():
    # Проверяем авторизацию (опционально)
    auth = request.headers.get('X-API-Key')
    if auth != os.environ.get('API_KEY', ''):
        return 'Unauthorized', 401
    
    result = {}
    for device_id, data in devices.items():
        last_seen = datetime.fromtimestamp(data['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
        result[device_id] = {'last_ping': last_seen, 'status': 'OK' if not data['alert_sent'] else 'ALERT'}
    return result
