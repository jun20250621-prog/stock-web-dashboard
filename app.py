#!/usr/bin/env python3
"""
台股智能分析系統 - 網頁版 (含排程設定)
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, template_folder='templates')
CORS(app)

# 載入設定
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'stock_cli', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # 修正資料庫路徑
            if 'database' in config and 'path' in config['database']:
                config['database']['path'] = os.path.join(os.path.dirname(__file__), config['database']['path'])
            return config
    return {}

config = load_config()

# 初始化模組
from data.fetcher import StockDataFetcher, TaiwanStockScreener
from data.portfolio import PortfolioManager
from data.watchlist import WatchlistManager
from data.trade_journal import TradeJournal
from data.strategy_lib import StrategyLibrary

fetcher = StockDataFetcher()
screener = TaiwanStockScreener()
pm = PortfolioManager(config)
wm = WatchlistManager(config)
tj = TradeJournal(config)
sl = StrategyLibrary(config)

# ==================== 路由 ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/portfolio')
def api_portfolio():
    portfolio = pm.get_all()
    stocks = []
    for code, stock in portfolio.items():
        price_data = screener.get_daily_price(code, 1)
        current_price = 0
        change_pct = 0
        if price_data:
            latest = price_data[-1]
            current_price = latest.get('close', 0)
            spread = latest.get('spread', 0) or 0
            change_pct = (spread / (current_price - spread)) * 100 if current_price > spread else 0
        pl = pm.calculate_profit_loss(code, current_price) if current_price > 0 else {'profit_loss': 0, 'profit_loss_pct': 0, 'stop_loss': 0, 'stop_profit': 0}
        stocks.append({
            'code': code,
            'name': stock.get('name'),
            'cost': stock.get('cost'),
            'current_price': current_price,
            'change_pct': round(change_pct, 2),
            'profit_loss': round(pl.get('profit_loss', 0), 2),
            'profit_loss_pct': round(pl.get('profit_loss_pct', 0), 2),
            'stop_loss': stock.get('stop_loss'),
            'stop_profit': stock.get('stop_profit'),
            'industry': stock.get('industry', ''),
            'strategy': get_strategy(pl)
        })
    return jsonify(stocks)

@app.route('/api/watchlist')
def api_watchlist():
    watchlist = wm.get_all()
    stocks = []
    for item in watchlist:
        code = item.get('code')
        price_data = screener.get_daily_price(code, 1)
        current_price = 0
        change_pct = 0
        if price_data:
            latest = price_data[-1]
            current_price = latest.get('close', 0)
            spread = latest.get('spread', 0) or 0
            change_pct = (spread / (current_price - spread)) * 100 if current_price > spread else 0
        stocks.append({
            'code': code,
            'name': item.get('name'),
            'current_price': current_price,
            'target_price': item.get('target_price'),
            'change_pct': round(change_pct, 2),
            'reason': item.get('reason', ''),
            'industry': item.get('industry', '')
        })
    return jsonify(stocks)

@app.route('/api/trades')
def api_trades():
    filters = {}
    if request.args.get('stock'):
        filters['code'] = request.args.get('stock')
    trades = tj.get_trades(filters)
    return jsonify(trades)

@app.route('/api/trade_analysis')
def api_trade_analysis():
    try:
        year = request.args.get('year', type=int)
        analysis = tj.analyze_performance(year)
        return jsonify(analysis)
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/strategies')
def api_strategies():
    strategies = sl.get_strategies()
    return jsonify(strategies)

@app.route('/api/stock/<code>')
def api_stock(code):
    price_data = screener.get_daily_price(code, 30)
    if price_data and len(price_data) > 0:
        import pandas as pd
        df = pd.DataFrame(price_data)
        close = df['close'].fillna(0)
        df['ma5'] = close.rolling(5).mean().fillna(0)
        df['ma20'] = close.rolling(20).mean().fillna(0)
        df['ma60'] = close.rolling(60).mean().fillna(0)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        loss = loss.replace(0, 0.0001)
        rs = gain / loss
        df['rsi'] = (100 - (100 / (1 + rs))).fillna(50)
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        df['macd'] = (ema12 - ema26).fillna(0)
        df['signal'] = df['macd'].ewm(span=9).mean().fillna(0)
        return jsonify({
            'code': code,
            'labels': [str(p.get('date', '')) for p in price_data],
            'prices': [float(p.get('close', 0) or 0) for p in price_data],
            'ma5': [float(x) if not pd.isna(x) else None for x in df['ma5'].tolist()],
            'ma20': [float(x) if not pd.isna(x) else None for x in df['ma20'].tolist()],
            'ma60': [float(x) if not pd.isna(x) else None for x in df['ma60'].tolist()],
            'rsi': [float(x) if not pd.isna(x) else 50 for x in df['rsi'].tolist()],
            'macd': [float(x) if not pd.isna(x) else 0 for x in df['macd'].tolist()],
            'signal': [float(x) if not pd.isna(x) else 0 for x in df['signal'].tolist()],
            'k': [float(x) if not pd.isna(x) else 50 for x in df['macd'].tolist()],
            'd': [float(x) if not pd.isna(x) else 50 for x in df['signal'].tolist()]
        })
    return jsonify({'error': '無法取得資料'})

@app.route('/api/strong_stocks')
def api_strong_stocks():
    min_volume = request.args.get('min_volume', default=1000, type=int)
    min_price = request.args.get('min_price', default=10, type=float)
    stocks = screener.screen_strong_stocks(min_volume, min_price)
    return jsonify(stocks)

# ==================== 排程設定 API ====================

@app.route('/api/schedule', methods=['GET', 'POST'])
def api_schedule():
    config = load_config()
    schedule = config.get('schedule', {
        'morning': '08:30',
        'monitor': ['09:30', '10:30', '11:30', '13:00', '14:00'],
        'evening': '15:00'
    })
    
    if request.method == 'POST':
        data = request.json
        schedule = data.get('schedule', schedule)
        config['schedule'] = schedule
        config_path = os.path.join(os.path.dirname(__file__), 'stock_cli', 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True, 'schedule': schedule})
    
    return jsonify(schedule)

# ==================== CRUD API ====================

@app.route('/api/portfolio/add', methods=['POST'])
def api_portfolio_add():
    data = request.json
    code = data.get('code')
    pm.add(code, data)
    return jsonify({'success': True})

@app.route('/api/portfolio/update/<code>', methods=['POST'])
def api_portfolio_update(code):
    data = request.json
    pm.update(code, data)
    return jsonify({'success': True})

@app.route('/api/portfolio/delete/<code>', methods=['POST'])
def api_portfolio_delete(code):
    pm.remove(code)
    return jsonify({'success': True})

@app.route('/api/watchlist/add', methods=['POST'])
def api_watchlist_add():
    data = request.json
    wm.add(data)
    return jsonify({'success': True})

@app.route('/api/watchlist/delete/<code>', methods=['POST'])
def api_watchlist_delete(code):
    wm.remove(code)
    return jsonify({'success': True})

@app.route('/api/watchlist/update/<code>', methods=['POST'])
def api_watchlist_update(code):
    data = request.json
    wm.update(code, data)
    return jsonify({'success': True})

@app.route('/api/trade/add', methods=['POST'])
def api_trade_add():
    data = request.json
    try:
        trade_id = tj.add_trade(data)
        return jsonify({'success': True, 'id': trade_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/trade/update/<trade_id>', methods=['POST'])
def api_trade_update(trade_id):
    data = request.json
    tj.update_trade(trade_id, data)
    return jsonify({'success': True})

@app.route('/api/trade/delete/<trade_id>', methods=['POST'])
def api_trade_delete(trade_id):
    tj.delete_trade(trade_id)
    return jsonify({'success': True})

@app.route('/api/sample/generate', methods=['POST'])
def api_generate_sample():
    sample_trades = [
        {'code': '2330', 'name': '台積電', 'type': '買入', 'buy_date': '2025-01-10', 'buy_price': 1050, 'shares': 1000, 'sell_date': '2025-03-15', 'sell_price': 1180, 'entry_strategy_id': 'STG001', 'entry_reason': 'KD黃金交叉', 'result': '成功', 'success_reason': '趨勢判斷正確', 'discipline': '完全遵守', 'discipline_score': 95},
        {'code': '2454', 'name': '聯發科', 'type': '買入', 'buy_date': '2025-02-01', 'buy_price': 1380, 'shares': 500, 'sell_date': '2025-04-10', 'sell_price': 1290, 'entry_strategy_id': 'STG003', 'entry_reason': 'MA多頭排列', 'result': '失敗', 'failure_reason': '趨勢反轉太快', 'discipline': '部分遵守', 'discipline_score': 70},
        {'code': '2317', 'name': '鴻海', 'type': '買入', 'buy_date': '2025-01-20', 'buy_price': 185, 'shares': 2000, 'sell_date': '2025-06-01', 'sell_price': 210, 'entry_strategy_id': 'STG006', 'entry_reason': '價量齊揚', 'result': '成功', 'success_reason': '資金管理得當', 'discipline': '完全遵守', 'discipline_score': 88},
        {'code': '2382', 'name': '廣達', 'type': '買入', 'buy_date': '2025-03-01', 'buy_price': 280, 'shares': 1500, 'sell_date': '2025-03-20', 'sell_price': 265, 'entry_strategy_id': 'STG001', 'entry_reason': 'KD黃金交叉', 'result': '失敗', 'failure_reason': '過早進場', 'discipline': '未遵守', 'discipline_score': 45},
        {'code': '3711', 'name': '日月光', 'type': '買入', 'buy_date': '2025-04-01', 'buy_price': 195, 'shares': 3000, 'sell_date': '2025-07-01', 'sell_price': 230, 'entry_strategy_id': 'STG004', 'entry_reason': 'RSI超賣反彈', 'result': '成功', 'success_reason': '嚴守停損停利紀律', 'discipline': '完全遵守', 'discipline_score': 92},
    ]
    for t in sample_trades:
        try:
            tj.add_trade(t)
        except:
            pass
    return jsonify({'success': True, 'count': len(sample_trades)})

# ==================== 輔助函數 ====================

def get_strategy(pl):
    pct = pl.get('profit_loss_pct', 0)
    current = pl.get('current_price', 0)
    stop_loss = pl.get('stop_loss', 0)
    stop_profit = pl.get('stop_profit', 0)
    if stop_loss and current <= stop_loss:
        return '🛑 觸及停損'
    elif stop_profit and current >= stop_profit:
        return '✅ 觸及停利'
    elif pct >= 10:
        return '🎯 漲多'
    elif pct >= 5:
        return '✅ 續抱'
    elif pct >= 0:
        return '🔸 續抱等解套'
    elif pct >= -5:
        return '⚠️ 留意'
    else:
        return '🛑 建議停損'

# ==================== Main ====================

if __name__ == '__main__':
    print("🚀 啟動網頁版儀表板...")
    print("📍 http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
