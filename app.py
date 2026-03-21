#!/usr/bin/env python3
"""
台股智能分析系統 - 網頁版 (含排程設定)
Version: 1.0.0
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sys
import os
import json
import base64
import io
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from apscheduler.schedulers.background import BackgroundScheduler
import threading

from data.stock_master import StockMaster, fetch_stock_info, calculate_target_price

# 台灣時區 (UTC+8)
def now_taiwan():
    return datetime.now(timezone(timedelta(hours=8)))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, template_folder='templates')
CORS(app)

# 全域變數
config = {}
pm = None  # PortfolioManager
wm = None  # WatchlistManager
tj = None  # TradeJournal

# 載入設定
def load_config():
    global config
    config_path = os.path.join(os.path.dirname(__file__), 'stock_cli', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            new_config = json.load(f)
            # 修正資料庫路徑
            if 'database' in new_config and 'path' in new_config['database']:
                new_config['database']['path'] = os.path.join(os.path.dirname(__file__), new_config['database']['path'])
            config = new_config
    return config

# 重新載入設定（用於更新後）
def reload_config():
    global config, pm, wm, tj
    load_config()
    # 重新初始化管理器（更新全域變數）
    pm = PortfolioManager(config)
    wm = WatchlistManager(config)
    tj = TradeJournal(config)

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
sm = StockMaster(config.get('database', {}).get('path', 'data/stock_data.db'))

# ==================== Yahoo Finance 工具 ====================

def get_yahoo_price(stock_code: str, days: int = 10) -> Optional[Dict]:
    """使用 Yahoo Finance 取得即時股價"""
    from datetime import datetime
    
    try:
        # 上市: 2331.TW, 櫃買: 5392.TWO, ETF: 00687B.TW
        # 修正：只有 00687B 這種代碼結尾是 B 的才是 ETF
        symbol = f"{stock_code}.TW"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={days}d"
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError:
            # 嘗試櫃買
            symbol = f"{stock_code}.TWO"
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={days}d"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
        
        if 'chart' in data and data['chart']['result']:
            result = data['chart']['result'][0]
            meta = result.get('meta', {})
            quote = result.get('indicators', {}).get('quote', [{}])[0]
            
            if not meta.get('regularMarketPrice'):
                return None
            
            current_price = meta.get('regularMarketPrice', 0)
            
            # 從 K 線資料計算漲跌幅
            # 修正：找到最近一個「不同」的收盤價（解決週末重複值的問題）
            closes = [c for c in quote.get('close', []) if c is not None]
            if len(closes) >= 2:
                # 從後往前找第一個明顯不同的收盤價（避開浮點精度問題）
                prev_close = current_price
                epsilon = 0.001  # 忽略小於 0.1% 的差異
                for c in reversed(closes[:-1]):
                    if abs(c - current_price) / current_price > epsilon:
                        prev_close = c
                        break
            else:
                prev_close = current_price
            
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0
            
            # 取得 K 線資料
            closes = quote.get('close', [])
            opens = quote.get('open', [])
            highs = quote.get('high', [])
            lows = quote.get('low', [])
            timestamps = result.get('timestamp', [])
            
            price_data = []
            from datetime import datetime
            for i in range(len(closes)):
                if closes[i] is not None:
                    price_data.append({
                        'close': closes[i],
                        'open': opens[i] if i < len(opens) and opens[i] else closes[i],
                        'high': highs[i] if i < len(highs) and highs[i] else closes[i],
                        'low': lows[i] if i < len(lows) and lows[i] else closes[i],
                        'date': datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d') if i < len(timestamps) else ''
                    })
            
            return {
                'price': current_price,
                'change': change,
                'change_pct': change_pct,
                'price_data': price_data
            }
    except Exception as e:
        print(f"Yahoo price error for {stock_code}: {e}")
    
    return None

# ==================== 路由 ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/portfolio')
def api_portfolio():
    portfolio = pm.get_all()
    stocks = []
    for stock in portfolio:
        code = stock.get('code')
        
        # 使用 Yahoo Finance 取得即時報價
        yahoo_data = get_yahoo_price(code)
        current_price = 0
        change_pct = 0
        if yahoo_data:
            current_price = yahoo_data.get('price', 0)
            change_pct = yahoo_data.get('change_pct', 0)
        
        pl = pm.calculate_profit_loss(code, current_price) if current_price > 0 else {'profit_loss': 0, 'profit_loss_pct': 0, 'stop_loss': 0, 'stop_profit': 0}
        stocks.append({
            'code': code,
            'name': stock.get('name'),
            'cost': stock.get('cost'),
            'shares': stock.get('shares'),
            'current_price': current_price,
            'change_pct': round(change_pct, 2),
            'profit_loss': round(pl.get('profit_loss', 0), 2),
            'profit_loss_pct': round(pl.get('profit_loss_pct', 0), 2),
            'stop_loss': stock.get('stop_loss'),
            'stop_profit': stock.get('stop_profit'),
            'industry': stock.get('industry', ''),
            'application': stock.get('application', ''),
            'buy_date': stock.get('buy_date', ''),
            'strategy': get_strategy(pl)
        })
    return jsonify(stocks)

@app.route('/api/watchlist')
def api_watchlist():
    try:
        watchlist = wm.get_all()
        stocks = []
        for item in watchlist:
            code = item.get('code')
            
            # 使用 Yahoo Finance 取得即時報價
            yahoo_data = get_yahoo_price(code)
            current_price = 0
            change_pct = 0
            if yahoo_data:
                current_price = yahoo_data.get('price', 0)
                change_pct = yahoo_data.get('change_pct', 0)
            
            stocks.append({
                'code': code,
                'name': item.get('name'),
                'current_price': current_price,
                'target_price': item.get('target_price'),
                'change_pct': round(change_pct, 2),
                'reason': item.get('reason', ''),
                'industry': item.get('industry', ''),
                'add_date': item.get('add_date', '')
            })
        return jsonify(stocks)
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

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
    yahoo_data = get_yahoo_price(code, 60)  # K 線需要 60 天資料
    price_data = []
    if yahoo_data and yahoo_data.get('price_data'):
        price_data = yahoo_data['price_data']
    
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
    # 只篩選熱門股票以加快速度
    popular_stocks = []  # 使用全部股票篩選
    stocks = screener.screen_strong_stocks(min_volume, min_price, limit=50)
    return jsonify(stocks[:20] if len(stocks) > 20 else stocks)

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
    try:
        data = request.json
        code = data.get('code')
        if not code:
            return jsonify({'success': False, 'error': 'Missing code'}), 400
        
        # 檢查是否已存在
        existing = pm.get_all()
        if any(s.get('code') == code for s in existing):
            return jsonify({'success': False, 'error': f'股票 {code} 已經存在，不能重複新增'}), 400
        
        pm.add(code, data)
        reload_config()
        return jsonify({'success': True})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/portfolio/update/<code>', methods=['POST'])
def api_portfolio_update(code):
    try:
        data = request.json
        pm.update(code, data)
        reload_config()
        return jsonify({'success': True})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/portfolio/delete/<code>', methods=['POST'])
def api_portfolio_delete(code):
    pm.remove(code)
    reload_config()
    return jsonify({'success': True})

@app.route('/api/watchlist/add', methods=['POST'])
def api_watchlist_add():
    try:
        data = request.json
        code = data.get('code')
        
        # 檢查是否已存在
        existing = wm.get_all()
        if any(item.get('code') == code for item in existing):
            return jsonify({'success': False, 'error': f'股票 {code} 已經在觀察名單中'}), 400
        
        # 自動抓取股票資料
        stock_info = sm.fetch_and_save(code)
        
        if stock_info:
            # 填入股名、產業、現價
            data['name'] = stock_info.get('name', data.get('name', ''))
            data['industry'] = stock_info.get('industry', data.get('industry', ''))
            
            # 計算目標價
            target_prices = calculate_target_price(stock_info)
            data['target_price'] = target_prices.get('graham') or target_prices.get('eps_15') or data.get('target_price')
            data['target_prices'] = target_prices  # 全部目標價回傳給前端
            data['stock_info'] = {
                'price': stock_info.get('price'),
                'change_pct': stock_info.get('change_pct'),
                'pe': stock_info.get('pe'),
                'high_52w': stock_info.get('high_52w'),
                'low_52w': stock_info.get('low_52w')
            }
        else:
            # 抓不到資料時，使用手動輸入
            pass
        
        wm.add(data)
        reload_config()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/stock/lookup/<code>', methods=['GET'])
def api_stock_lookup(code):
    """查詢股票資料並計算目標價"""
    try:
        # 先嘗試從資料庫取得
        stock_info = sm.get(code)
        
        if not stock_info:
            # 抓不到則從網路抓
            stock_info = sm.fetch_and_save(code)
        
        if not stock_info:
            return jsonify({'success': False, 'error': '無法取得股票資料'}), 404
        
        # 計算目標價
        target_prices = calculate_target_price(stock_info)
        
        return jsonify({
            'success': True,
            'stock': stock_info,
            'target_prices': target_prices
        })
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/watchlist/delete/<code>', methods=['POST'])
def api_watchlist_delete(code):
    wm.remove(code)
    reload_config()
    return jsonify({'success': True})

@app.route('/api/watchlist/update/<code>', methods=['POST'])
def api_watchlist_update(code):
    try:
        data = request.json
        wm.update(code, data)
        reload_config()
        return jsonify({'success': True})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

# ==================== 投資策略 API ====================

@app.route('/api/strategy/<code>', methods=['GET'])
def api_strategy_get(code):
    """取得股票的所有策略"""
    try:
        conn = sqlite3.connect(config.get('database', {}).get('path', 'data/stock_data.db'))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM stock_strategy 
            WHERE stock_code = ? 
            ORDER BY strategy_type, batch_num
        ''', (code,))
        
        strategies = [dict(row) for row in cursor.fetchall()]
        
        # 取得股票基本資料
        cursor.execute('SELECT name FROM stock WHERE code = ?', (code,))
        row = cursor.fetchone()
        stock_name = row['name'] if row else code
        
        conn.close()
        return jsonify({
            'success': True,
            'stock_code': code,
            'stock_name': stock_name,
            'strategies': strategies
        })
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/strategy', methods=['POST'])
def api_strategy_add():
    """新增策略"""
    try:
        data = request.json
        stock_code = data.get('stock_code')
        strategy_type = data.get('strategy_type')  # '進場' or '賣出'
        batch_num = data.get('batch_num')
        price = data.get('price')
        shares = data.get('shares')
        description = data.get('description', '')
        status = data.get('status', '未買')
        
        conn = sqlite3.connect(config.get('database', {}).get('path', 'data/stock_data.db'))
        cursor = conn.cursor()
        
        # 檢查該類型策略是否已滿 5 批
        cursor.execute('''
            SELECT COUNT(*) FROM stock_strategy 
            WHERE stock_code = ? AND strategy_type = ?
        ''', (stock_code, strategy_type))
        count = cursor.fetchone()[0]
        if count >= 5:
            conn.close()
            return jsonify({'success': False, 'error': f'{strategy_type}策略最多 5 批'}), 400
        
        cursor.execute('''
            INSERT INTO stock_strategy (stock_code, strategy_type, batch_num, price, shares, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (stock_code, strategy_type, batch_num, price, shares, description, status))
        
        strategy_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'id': strategy_id})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/strategy/<int:strategy_id>', methods=['PUT'])
def api_strategy_update(strategy_id):
    """更新策略"""
    try:
        data = request.json
        conn = sqlite3.connect(config.get('database', {}).get('path', 'data/stock_data.db'))
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE stock_strategy 
            SET batch_num = ?, price = ?, shares = ?, description = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (data.get('batch_num'), data.get('price'), data.get('shares'), data.get('description'), data.get('status'), strategy_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/strategy/<int:strategy_id>', methods=['DELETE'])
def api_strategy_delete(strategy_id):
    """刪除策略"""
    try:
        conn = sqlite3.connect(config.get('database', {}).get('path', 'data/stock_data.db'))
        cursor = conn.cursor()
        cursor.execute('DELETE FROM stock_strategy WHERE id = ?', (strategy_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trade/add', methods=['POST'])
def api_trade_add():
    data = request.json
    try:
        trade_id = tj.add_trade(data)
        reload_config()
        return jsonify({'success': True, 'id': trade_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/trade/update/<trade_id>', methods=['POST'])
def api_trade_update(trade_id):
    try:
        data = request.json
        tj.update_trade(trade_id, data)
        reload_config()
        return jsonify({'success': True})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/trade/delete/<trade_id>', methods=['POST'])
def api_trade_delete(trade_id):
    tj.delete_trade(trade_id)
    reload_config()
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

# ==================== 匯出/匯入功能 ====================

def create_excel(data, columns, filename):
    """建立 Excel 檔案"""
    try:
        import pandas as pd
        df = pd.DataFrame(data)
        # 選擇需要的欄位
        df = df[[c for c in columns if c in df.columns]]
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        output.seek(0)
        b64_data = base64.b64encode(output.getvalue()).decode('utf-8')
        return {'data': b64_data, 'filename': filename}
    except Exception as e:
        return {'error': str(e)}

@app.route('/api/export/portfolio')
def api_export_portfolio():
    """匯出持股"""
    portfolio = pm.get_all()
    data = []
    for stock in portfolio:
        code = stock.get('code')
        data.append({
            '股票代碼': code,
            '股票名稱': stock.get('name', ''),
            '成本價': stock.get('cost', 0),
            '股數': stock.get('shares', 0),
            '停損價': stock.get('stop_loss', ''),
            '停利價': stock.get('stop_profit', ''),
            '產業': stock.get('industry', ''),
            '應用': stock.get('application', ''),
            '買入日期': stock.get('buy_date', '')
        })
    return jsonify(create_excel(data, ['股票代碼', '股票名稱', '成本價', '股數', '停損價', '停利價', '產業', '應用', '買入日期'], f'持股_{now_taiwan().strftime("%Y%m%d_%H%M%S")}.xlsx'))

@app.route('/api/export/trades')
def api_export_trades():
    """匯出交易紀錄"""
    # 策略代號對照表
    strategy_names = {
        'STG001': 'KD黃金交叉', 'STG002': 'KD死亡交叉', 'STG003': 'MA多頭排列',
        'STG004': 'RSI超賣反彈', 'STG005': 'MACD黃金交叉', 'STG006': '價量齊揚',
        'STG007': '突破整理平台', 'STG008': '殖利率策略', 'STG009': '營收成長'
    }
    trades = tj.get_trades()
    data = []
    for t in trades:
        strategy_id = t.get('entry_strategy_id', '')
        strategy_name = strategy_names.get(strategy_id, strategy_id)
        data.append({
            '股票代碼': t.get('code', ''),
            '股票名稱': t.get('name', ''),
            '買入日期': t.get('buy_date', ''),
            '買入價格': t.get('buy_price', 0),
            '賣出日期': t.get('sell_date', ''),
            '賣出價格': t.get('sell_price', 0),
            '股數': t.get('shares', 0),
            '損益': t.get('profit_loss', 0),
            '損益率': t.get('profit_loss_pct', 0),
            '結果': t.get('result', ''),
            '紀律': t.get('discipline', ''),
            '策略': strategy_name
        })
    return jsonify(create_excel(data, ['股票代碼', '股票名稱', '買入日期', '買入價格', '賣出日期', '賣出價格', '股數', '損益', '損益率', '結果', '紀律', '策略'], f'交易紀錄_{now_taiwan().strftime("%Y%m%d_%H%M%S")}.xlsx'))

@app.route('/api/export/watchlist')
def api_export_watchlist():
    """匯出觀察名單"""
    watchlist = wm.get_all()
    data = []
    for w in watchlist:
        data.append({
            '股票代碼': w.get('code', ''),
            '股票名稱': w.get('name', ''),
            '目標價': w.get('target_price', ''),
            '追蹤原因': w.get('reason', ''),
            '產業': w.get('industry', ''),
            '新增日期': w.get('add_date', '')
        })
    return jsonify(create_excel(data, ['股票代碼', '股票名稱', '目標價', '追蹤原因', '產業', '新增日期'], f'觀察名單_{now_taiwan().strftime("%Y%m%d_%H%M%S")}.xlsx'))

@app.route('/api/import/trades', methods=['POST'])
def api_import_trades():
    """匯入交易紀錄"""
    try:
        import pandas as pd
        data = request.json
        b64_data = data.get('data', '')
        if not b64_data:
            return jsonify({'success': False, 'error': '無檔案資料'})
        
        # 解碼 Base64
        excel_data = base64.b64decode(b64_data)
        df = pd.read_excel(io.BytesIO(excel_data))
        
        # 支援的中文/英文欄位名稱映射
        col_map = {
            'code': ['股票代碼', 'code', 'Code', '代碼'],
            'name': ['股票名稱', 'name', 'Name', '名稱'],
            'buy_date': ['買入日期', 'buy_date', 'Buy Date', '買日'],
            'buy_price': ['買入價格', 'buy_price', 'Buy Price', '買價'],
            'sell_date': ['賣出日期', 'sell_date', 'Sell Date', '賣日'],
            'sell_price': ['賣出價格', 'sell_price', 'Sell Price', '賣價'],
            'shares': ['股數', 'shares', 'Shares', '數量'],
            'result': ['結果', 'result', 'Result', '勝敗'],
            'discipline': ['紀律', 'discipline', 'Discipline'],
            'entry_strategy_id': ['策略', 'strategy', 'Strategy', 'entry_strategy_id']
        }
        
        def get_val(row, keys):
            for k in keys:
                if k in row.index:
                    val = row[k]
                    if pd.notna(val):
                        return val
            return None
        
        # 匯入每一筆
        count = 0
        errors = []
        for idx, row in df.iterrows():
            try:
                trade_data = {
                    'code': str(get_val(row, col_map['code']) or ''),
                    'name': str(get_val(row, col_map['name']) or ''),
                    'buy_date': str(get_val(row, col_map['buy_date']) or ''),
                    'buy_price': float(get_val(row, col_map['buy_price'])) if get_val(row, col_map['buy_price']) else None,
                    'sell_date': str(get_val(row, col_map['sell_date'])) if get_val(row, col_map['sell_date']) else None,
                    'sell_price': float(get_val(row, col_map['sell_price'])) if get_val(row, col_map['sell_price']) else None,
                    'shares': int(get_val(row, col_map['shares'])) if get_val(row, col_map['shares']) else None,
                    'result': str(get_val(row, col_map['result']) or ''),
                    'discipline': str(get_val(row, col_map['discipline']) or ''),
                    'entry_strategy_id': str(get_val(row, col_map['entry_strategy_id']) or '')
                }
                if trade_data['code'] and trade_data['code'] != 'nan':
                    tj.add_trade(trade_data)
                    count += 1
                else:
                    errors.append(f'Row {idx+1}: Missing code')
            except Exception as e:
                errors.append(f'Row {idx+1}: {str(e)}')
        
        reload_config()
        return jsonify({'success': True, 'count': count, 'errors': errors[:5] if errors else []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/import/watchlist', methods=['POST'])
def api_import_watchlist():
    """匯入觀察名單"""
    try:
        import pandas as pd
        data = request.json
        b64_data = data.get('data', '')
        if not b64_data:
            return jsonify({'success': False, 'error': '無檔案資料'})
        
        # 解碼 Base64
        excel_data = base64.b64decode(b64_data)
        df = pd.read_excel(io.BytesIO(excel_data))
        
        # 支援的中文/英文欄位名稱映射
        col_map = {
            'code': ['股票代碼', 'code', 'Code', '代碼'],
            'name': ['股票名稱', 'name', 'Name', '名稱'],
            'target_price': ['目標價', 'target_price', 'Target Price', '目標'],
            'reason': ['追蹤原因', 'reason', 'Reason', '原因'],
            'industry': ['產業', 'industry', 'Industry'],
            'add_date': ['新增日期', 'add_date', 'Add Date', '日期']
        }
        
        def get_val(row, keys):
            for k in keys:
                if k in row.index:
                    val = row[k]
                    if pd.notna(val):
                        return val
            return None
        
        # 匯入每一筆
        count = 0
        errors = []
        for idx, row in df.iterrows():
            try:
                item = {
                    'code': str(get_val(row, col_map['code']) or ''),
                    'name': str(get_val(row, col_map['name']) or ''),
                    'target_price': float(get_val(row, col_map['target_price'])) if get_val(row, col_map['target_price']) else None,
                    'reason': str(get_val(row, col_map['reason']) or ''),
                    'industry': str(get_val(row, col_map['industry']) or ''),
                    'add_date': str(get_val(row, col_map['add_date']) or now_taiwan().strftime('%Y-%m-%d'))
                }
                if item['code'] and item['code'] != 'nan':
                    wm.add(item)
                    count += 1
                else:
                    errors.append(f'Row {idx+1}: Missing code')
            except Exception as e:
                errors.append(f'Row {idx+1}: {str(e)}')
        
        reload_config()
        return jsonify({'success': True, 'count': count, 'errors': errors[:5] if errors else []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/import/portfolio', methods=['POST'])
def api_import_portfolio():
    """匯入持股"""
    try:
        import pandas as pd
        data = request.json
        b64_data = data.get('data', '')
        if not b64_data:
            return jsonify({'success': False, 'error': '無檔案資料'})
        
        # 解碼 Base64
        excel_data = base64.b64decode(b64_data)
        df = pd.read_excel(io.BytesIO(excel_data))
        
        # 支援的中文/英文欄位名稱映射
        col_map = {
            'code': ['股票代碼', 'code', 'Code', '代碼'],
            'name': ['股票名稱', 'name', 'Name', '名稱'],
            'cost': ['成本', 'cost', 'Cost', '買入價'],
            'shares': ['股數', 'shares', 'Shares', '數量'],
            'stop_loss': ['停損', 'stop_loss', 'Stop Loss'],
            'stop_profit': ['停利', 'stop_profit', 'Stop Profit'],
            'industry': ['產業', 'industry', 'Industry'],
            'application': ['應用', 'application', 'Application', '用途'],
            'buy_date': ['買入日期', 'buy_date', 'Buy Date', '買日']
        }
        
        def get_val(row, keys):
            for k in keys:
                if k in row.index:
                    val = row[k]
                    if pd.notna(val):
                        return val
            return None
        
        # 匯入每一筆
        count = 0
        errors = []
        for idx, row in df.iterrows():
            try:
                item = {
                    'code': str(get_val(row, col_map['code']) or ''),
                    'name': str(get_val(row, col_map['name']) or ''),
                    'cost': float(get_val(row, col_map['cost']) or 0),
                    'shares': int(get_val(row, col_map['shares']) or 1000),
                    'stop_loss': float(get_val(row, col_map['stop_loss']) or 0) or None,
                    'stop_profit': float(get_val(row, col_map['stop_profit']) or 0) or None,
                    'industry': str(get_val(row, col_map['industry']) or ''),
                    'application': str(get_val(row, col_map['application']) or ''),
                    'buy_date': str(get_val(row, col_map['buy_date']) or '')
                }
                
                if item['code']:
                    pm.add(item['code'], item)
                    count += 1
            except Exception as e:
                errors.append(f"第{idx+1}筆: {str(e)}")
        
        return jsonify({
            'success': True, 
            'count': count,
            'errors': errors[:5] if errors else []
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== 排程發送 Telegram ====================

TELEGRAM_TOKEN = '8294937993:AAFOY_rwU33p6ndhFrnDyjKFrSQ-_1KavOE'
TELEGRAM_CHAT_ID = '8137433836'

def send_telegram(message):
    """發送 Telegram 訊息"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=10)
        return True
    except Exception as e:
        print(f"Telegram send error: {e}")
        return False

def generate_report_message():
    """產生報報告訊息"""
    try:
        # 取得持股資料
        portfolio = pm.get_all()
        msg = "📊 <b>盤後報告</b>\n\n"
        msg += "🛑 <b>持股狀態：</b>\n"
        
        alert_stocks = []
        for stock in portfolio[:5]:
            code = stock.get('code')
            try:
                # 使用 Yahoo Finance
                yahoo_data = get_yahoo_price(code)
                current_price = yahoo_data.get('price', 0) if yahoo_data else 0
                if current_price > 0:
                    cost = stock.get('cost', 0)
                    if cost > 0:
                        pl_pct = ((current_price - cost) / cost) * 100
                        if pl_pct <= -5 or pl_pct >= 10:
                            name = stock.get('name', code)
                            emoji = "🟢" if pl_pct > 0 else "🔴"
                            alert_stocks.append(f"{emoji} {code} {name}: {current_price} ({pl_pct:+.2f}%)")
            except:
                pass
        
        if alert_stocks:
            msg += "\n".join(alert_stocks)
        else:
            msg += "✅ 無異常波動"
        
        return msg
    except Exception as e:
        return f"Error generating report: {e}"

def check_schedule():
    """檢查排程並發送"""
    try:
        schedule = config.get('schedule', {})
        now = now_taiwan()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")
        
        # 檢查早盤
        morning_time = schedule.get('morning', '08:30')
        if current_time == morning_time:
            msg = f"🌅 <b>早盤提醒</b> - {current_date}"
            send_telegram(msg)
        
        # 檢查監控時間
        monitor_times = schedule.get('monitor', [])
        if current_time in monitor_times:
            msg = generate_report_message()
            send_telegram(msg)
        
        # 檢查晚盤
        evening_time = schedule.get('evening', '15:00')
        if current_time == evening_time:
            msg = f"🌙 <b>盤後報告</b> - {current_date}\n\n" + generate_report_message()
            send_telegram(msg)
    except Exception as e:
        print(f"Schedule check error: {e}")

# 啟動排程器
scheduler = BackgroundScheduler()
scheduler.add_job(check_schedule, 'interval', minutes=1)
scheduler.start()

# ==================== Main ====================

if __name__ == '__main__':
    print("🚀 啟動網頁版儀表板...")
    print("📍 http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
