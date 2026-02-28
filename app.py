#!/usr/bin/env python3
"""
台股智能分析系統 - 網頁版 (含排程設定)
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sys
import os
import json
import base64
import io
from datetime import datetime, timezone, timedelta

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
            # 使用與 portfolio 相同的價格取得邏輯
            price_data = screener.get_daily_price(code, 5)
            current_price = 0
            change_pct = 0
            if price_data and len(price_data) > 0:
                latest = price_data[-1]
                current_price = latest.get('close', 0)
                # 計算漲跌幅 - 使用與 portfolio 相同的方式
                spread = latest.get('spread', 0) or 0
                change_pct = (spread / (current_price - spread)) * 100 if current_price > spread else 0
            
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
    # 熱門股票列表
    popular_stocks = [
        {'code': '2330', 'name': '台積電', 'industry': '半導體'},
        {'code': '2454', 'name': '聯發科', 'industry': 'IC設計'},
        {'code': '2317', 'name': '鴻海', 'industry': '電子'},
        {'code': '2382', 'name': '廣達', 'industry': '電子'},
        {'code': '3711', 'name': '日月光', 'industry': '半導體'},
        {'code': '3034', 'name': '聯詠', 'industry': 'IC設計'},
        {'code': '3017', 'name': '奇鋐', 'industry': '散熱'},
        {'code': '3231', 'name': '緯創', 'industry': '電子'},
        {'code': '4908', 'name': '前鼎', 'industry': '光電'},
        {'code': '4977', 'name': '眾達-KY', 'industry': '光電'},
        {'code': '1590', 'name': '亞德客-KY', 'industry': '氣動'},
        {'code': '2630', 'name': '亞航', 'industry': '航太'},
    ]
    
    results = []
    for stock in popular_stocks:
        try:
            # 使用與 portfolio 相同的方式取得股價
            price_data = screener.get_daily_price(stock['code'], 10)
            if price_data and len(price_data) > 0:
                current = price_data[-1].get('close', 0)
                if len(price_data) >= 2:
                    prev = price_data[-2].get('close', current)
                    change_pct = ((current - prev) / prev * 100) if prev > 0 else 0
                else:
                    change_pct = 0
                
                # 計算5日動能
                momentum_5d = 0
                if len(price_data) >= 6:
                    p_start = price_data[-6].get('close', 0)
                    p_end = price_data[-1].get('close', 0)
                    if p_start > 0:
                        momentum_5d = ((p_end - p_start) / p_start) * 100
                
                if current > 0:
                    results.append({
                        'code': stock['code'],
                        'name': stock['name'],
                        'industry': stock['industry'],
                        'price': current,
                        'change_pct': round(change_pct, 2),
                        'momentum_5d': round(momentum_5d, 2)
                    })
        except Exception as e:
            print(f"Error {stock['code']}: {e}")
    
    # 按動能排序
    results.sort(key=lambda x: x.get('momentum_5d', 0), reverse=True)
    return jsonify(results[:20])

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
        wm.add(data)
        reload_config()
        return jsonify({'success': True})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500

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
    for code, stock in portfolio.items():
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

@app.route('/api/import/portfolio', methods=['POST'])
def api_import_portfolio():
    """匯入持股"""
    try:
        import pandas as pd
        data = request.json
        b64_data = data.get('data', '')
        if not b64_data:
            return jsonify({'success': False, 'error': '無檔案資料'})
        
        excel_data = base64.b64decode(b64_data)
        df = pd.read_excel(io.BytesIO(excel_data))
        
        col_map = {
            'code': ['股票代碼', 'code', 'Code', '代碼'],
            'name': ['股票名稱', 'name', 'Name', '名稱'],
            'cost': ['成本價', 'cost', 'Cost'],
            'shares': ['股數', 'shares', 'Shares', '數量'],
            'stop_loss': ['停損價', 'stop_loss', 'Stop Loss'],
            'stop_profit': ['停利價', 'stop_profit', 'Stop Profit'],
            'industry': ['產業', 'industry', 'Industry'],
            'application': ['應用', 'application', 'Application'],
            'buy_date': ['買入日期', 'buy_date', 'Buy Date', '買日']
        }
        
        def get_val(row, keys):
            for k in keys:
                if k in row.index:
                    val = row[k]
                    if pd.notna(val):
                        return val
            return None
        
        count = 0
        for idx, row in df.iterrows():
            try:
                item = {
                    'code': str(get_val(row, col_map['code']) or ''),
                    'name': str(get_val(row, col_map['name']) or ''),
                    'cost': float(get_val(row, col_map['cost'])) if get_val(row, col_map['cost']) else 0,
                    'shares': int(get_val(row, col_map['shares'])) if get_val(row, col_map['shares']) else 1000,
                    'stop_loss': float(get_val(row, col_map['stop_loss'])) if get_val(row, col_map['stop_loss']) else None,
                    'stop_profit': float(get_val(row, col_map['stop_profit'])) if get_val(row, col_map['stop_profit']) else None,
                    'industry': str(get_val(row, col_map['industry']) or ''),
                    'application': str(get_val(row, col_map['application']) or ''),
                    'buy_date': str(get_val(row, col_map['buy_date']) or '')
                }
                if item['code'] and item['code'] != 'nan':
                    pm.add(item['code'], item)
                    count += 1
            except Exception as e:
                print(f"Row {idx} error: {e}")
        
        reload_config()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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

from datetime import datetime, timezone, timedelta

# 台灣時區 (UTC+8)
def now_taiwan():
    return datetime.now(timezone(timedelta(hours=8)))

# ==================== 排程發送 Telegram ====================

TELEGRAM_TOKEN = '8294937993:AAFOY_rwU33p6ndhFrnDyjKFrSQ-_1KavOE'
TELEGRAM_CHAT_ID = '8137433836'

def send_telegram(message):
    """發送 Telegram 訊息"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.post(url, data=data, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def generate_report_message():
    """產生報告訊息"""
    try:
        portfolio = pm.get_all()
        msg = "📊 <b>持股報告</b>\n\n"
        
        for code, stock in list(portfolio.items())[:10]:
            try:
                price_data = screener.get_daily_price(code, 1)
                if price_data:
                    current_price = price_data[-1].get('close', 0)
                    cost = stock.get('cost', 0)
                    shares = stock.get('shares', 1000)
                    if cost > 0:
                        pl = (current_price - cost) * shares
                        pl_pct = ((current_price - cost) / cost) * 100
                        emoji = "🟢" if pl >= 0 else "🔴"
                        msg += f"{emoji} {code} {stock.get('name','')}: {current_price} ({pl_pct:+.1f}%)\n"
            except:
                pass
        
        if len(portfolio) > 10:
            msg += f"\n...還有 {len(portfolio)-10} 筆"
        
        return msg
    except Exception as e:
        return f"Error: {e}"

def check_schedule():
    """檢查排程並發送"""
    try:
        schedule = config.get('schedule', {})
        now = now_taiwan()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")
        
        # 早盤
        if current_time == schedule.get('morning', '08:30'):
            send_telegram(f"🌅 <b>早盤提醒</b>\n\n今日日期: {current_date}\n\n記得追蹤大盤走勢！")
        
        # 監控時間
        monitor_times = schedule.get('monitor', '').split(',')
        if current_time in [t.strip() for t in monitor_times]:
            send_telegram(generate_report_message())
        
        # 晚盤
        if current_time == schedule.get('evening', '15:00'):
            msg = f"🌙 <b>盤後報告</b> - {current_date}\n\n" + generate_report_message()
            send_telegram(msg)
    except Exception as e:
        print(f"Schedule check error: {e}")

# 嘗試啟動排程器
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_schedule, 'interval', minutes=1)
    scheduler.start()
    print("✅ 排程器已啟動")
except Exception as e:
    print(f"⚠️ 排程器無法啟動: {e}")

# ==================== 股價快取 ====================
price_cache = {}
price_cache_time = {}

def get_cached_price(code):
    """取得快取股價"""
    import time
    now = time.time()
    # 5分鐘內不重複取得
    if code in price_cache and (now - price_cache_time.get(code, 0)) < 300:
        return price_cache[code]
    return None

def set_cached_price(code, price_data):
    """設定股價快取"""
    import time
    price_cache[code] = price_data
    price_cache_time[code] = time.time()

# ==================== 備份功能 ====================

@app.route('/api/backup')
def api_backup():
    """匯出完整資料庫備份"""
    try:
        db_path = config.get('database', {}).get('path', 'data/stock_data.db')
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(__file__), db_path)
        
        if os.path.exists(db_path):
            with open(db_path, 'rb') as f:
                db_data = base64.b64encode(f.read()).decode('utf-8')
            return jsonify({
                'success': True,
                'data': db_data,
                'filename': f'backup_{now_taiwan().strftime("%Y%m%d_%H%M%S")}.db',
                'tables': ['portfolio', 'watchlist', 'trades']
            })
        return jsonify({'success': False, 'error': 'Database not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/backup/restore', methods=['POST'])
def api_backup_restore():
    """從備份還原"""
    try:
        data = request.json
        db_data = data.get('data', '')
        if not db_data:
            return jsonify({'success': False, 'error': 'No data'})
        
        db_path = config.get('database', {}).get('path', 'data/stock_data.db')
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(__file__), db_path)
        
        # 寫入資料庫
        with open(db_path, 'wb') as f:
            f.write(base64.b64decode(db_data))
        
        # 重新載入
        reload_config()
        
        return jsonify({'success': True, 'message': 'Restore successful'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== Main ====================

if __name__ == '__main__':
    print("🚀 啟動網頁版儀表板...")
    print("📍 http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
