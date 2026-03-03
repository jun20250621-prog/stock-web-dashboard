#!/usr/bin/env python3
"""
台股智能分析系統 - 網頁版 (含排程設定)
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sys
import os
import json
import requests
import urllib.request
from datetime import datetime, timedelta, timezone

app = Flask(__name__, template_folder='templates')
CORS(app)

# 載入設定
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()

# ==================== iTick API 設定 ====================
ITICK_API_KEY = "ae7824e15cc34160bfe303310973ea9a77ee3c6b1c314202b2ff1bd23db02729"
ITICK_BASE_URL = "https://api.itick.org"

def get_itick_price(stock_id):
    """使用 iTick API 取得股票報價"""
    if stock_id.startswith('00') or stock_id.endswith('B'):
        return None  # iTick 不支援 ETF
    
    try:
        import urllib.parse
        url = f"{ITICK_BASE_URL}/stock/quote"
        params = urllib.parse.urlencode({"region": "TW", "code": stock_id})
        
        headers = {'accept': 'application/json', 'token': ITICK_API_KEY}
        req = urllib.request.Request(f"{url}?{params}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('code') == 0 and data.get('data'):
                d = data['data']
                return {
                    'price': d.get('p', 0),
                    'change_pct': d.get('chp', 0)
                }
    except Exception as e:
        pass
    return None

# ==================== 股價取得 ====================

def get_date_range(days=60):
    taiwan_tz = timezone(timedelta(hours=8))
    today = datetime.now(taiwan_tz).date()
    start_date = (today - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    return start_date, end_date

def get_stock_price(stock_id):
    """取得單一股票股價 - 優先使用 iTick"""
    # 先嘗試 iTick
    itick_data = get_itick_price(stock_id)
    if itick_data and itick_data.get('price'):
        return itick_data
    
    # Fallback 到 FinMind
    try:
        start_date, end_date = get_date_range(60)
        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id={stock_id}&start_date={start_date}&end_date={end_date}"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        if not data.get('data') or len(data['data']) == 0:
            return None
        
        items = data['data']
        latest = items[-1]
        prev = items[-2] if len(items) >= 2 else latest
        
        price = float(latest.get('close', 0))
        prev_price = float(prev.get('close', 0))
        change_pct = ((price - prev_price) / prev_price * 100) if prev_price else 0
        
        return {
            'price': price,
            'change_pct': change_pct
        }
    except Exception as e:
        print(f"Error getting {stock_id}: {e}")
        return None

# ==================== 路由 ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/portfolio')
def api_portfolio():
    portfolio = config.get('portfolio', {})
    stocks = []
    for code, stock in portfolio.items():
        # 取得現價
        price_data = get_stock_price(code)
        current_price = price_data.get('price') if price_data else None
        change_pct = price_data.get('change_pct') if price_data else None
        
        # 計算損益
        cost = stock.get('cost', 0)
        if current_price and cost:
            profit = (current_price - cost) * (stock.get('shares', 1000))
            profit_pct = (current_price - cost) / cost * 100
            profit_loss = f"${profit:+,.0f} ({profit_pct:+.1f}%)"
        else:
            profit_loss = "-"
        
        stocks.append({
            'code': code,
            'name': stock.get('name'),
            'cost': stock.get('cost'),
            'shares': stock.get('shares'),
            'current_price': f"${current_price:.0f}" if current_price else "-",
            'change_pct': f"{change_pct:+.2f}%" if change_pct is not None else "-",
            'profit_loss': profit_loss,
            'stop_loss': stock.get('stop_loss'),
            'stop_profit': stock.get('stop_profit'),
            'strategy': ''
        })
    return jsonify(stocks)

@app.route('/api/schedule', methods=['GET', 'POST'])
def api_schedule():
    if request.method == 'POST':
        data = request.json
        config['schedule'] = data.get('schedule', {})
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True})
    return jsonify(config.get('schedule', {
        'morning': '08:30',
        'monitor': '09:30,10:30,11:30,13:00,14:00',
        'evening': '15:00'
    }))

@app.route('/api/telegram/send', methods=['POST'])
def send_telegram():
    """手動發送 Telegram 報告"""
    data = request.json
    token = config.get('telegram', {}).get('bot_token')
    chat_id = config.get('telegram', {}).get('chat_id')
    
    if not token or not chat_id:
        return jsonify({'success': False, 'error': '未設定 Telegram'})
    
    message = data.get('message', '測試訊息')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": message})
    return jsonify({'success': resp.status_code == 200})

# ==================== 匯入匯出 API ====================

@app.route('/api/import/portfolio', methods=['POST'])
def import_portfolio():
    """匯入持股資料"""
    try:
        data = request.json.get('data', '')
        if not data:
            return jsonify({'success': False, 'error': '無資料'})
        
        import base64
        try:
            json_str = base64.b64decode(data).decode('utf-8')
        except:
            # 嘗試直接解碼（如果已經是 JSON 字串）
            json_str = data
        
        try:
            portfolio = json.loads(json_str)
        except:
            return jsonify({'success': False, 'error': '資料格式錯誤，請確認匯出格式正確'})
        
        config['portfolio'] = portfolio
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/import/watchlist', methods=['POST'])
def import_watchlist():
    """匯入觀察名單"""
    try:
        data = request.json.get('data', '')
        if not data:
            return jsonify({'success': False, 'error': '無資料'})
        
        import base64
        try:
            json_str = base64.b64decode(data).decode('utf-8')
        except:
            json_str = data
        
        watchlist = json.loads(json_str)
        config['watchlist'] = watchlist
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/import/trades', methods=['POST'])
def import_trades():
    """匯入交易紀錄"""
    try:
        data = request.json.get('data', '')
        if not data:
            return jsonify({'success': False, 'error': '無資料'})
        
        import base64
        try:
            json_str = base64.b64decode(data).decode('utf-8')
        except:
            json_str = data
        
        trades = json.loads(json_str)
        config['trades'] = trades
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    print("🚀 啟動網頁版...")
    print("📍 http://localhost:5000")
    app.run(host='0.0.0.0', port=5000)
