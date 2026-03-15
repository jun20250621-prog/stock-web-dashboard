#!/usr/bin/env python3
"""
股票監控與分析系統 - v2.0 (優化版)
更新：
- 修復重複函數問題
- 添加 logging
- 環境變數支援
- 程式碼優化
"""

import urllib.request
import json
import time
import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# ==================== Logging 設定 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 環境變數 ====================
DB_PATH = os.environ.get('DB_PATH', '/home/node/.openclaw/workspace/stock_web_deploy/data/stock_data.db')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8294937993:AAFOY_rwU33p6ndhFrnDyjKFrSQ-_1KavOE')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '8137433836')
CACHE_FILE = "/tmp/stock_cache_v2.json"
CACHE_TIMEOUT = 300

# ==================== 共用函數 ====================

def fetch_url(url: str, retries: int = 3) -> Optional[str]:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            logger.warning(f"fetch_url 失敗 (嘗試 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(1)
                continue
    return None

def get_date_range(days: int = 30) -> tuple:
    taiwan_tz = timezone(timedelta(hours=8))
    today = datetime.now(taiwan_tz).date()
    start_date = (today - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    return start_date, end_date

def load_cache(key: str) -> Optional[Dict]:
    """載入快取"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
                if key in cache:
                    cached_time = cache[key].get('time', 0)
                    if time.time() - cached_time < CACHE_TIMEOUT:
                        return cache[key].get('data')
    except Exception as e:
        logger.warning(f"載入快取失敗: {e}")
    return None

def save_cache(key: str, data: Dict):
    """儲存快取"""
    try:
        cache = {}
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
        
        cache[key] = {'data': data, 'time': time.time()}
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        logger.warning(f"儲存快取失敗: {e}")

# ==================== 資料庫 ====================

def load_portfolio_from_db() -> Dict:
    """從 SQLite 載入持股"""
    portfolio = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, cost, shares, stop_loss, stop_profit, industry, application FROM portfolio")
        for row in cursor.fetchall():
            portfolio[row[0]] = {
                "name": row[1],
                "cost": row[2],
                "shares": row[3] or 1000,
                "stop_loss": row[4],
                "stop_profit": row[5],
                "industry": row[6] or "",
                "application": row[7] or ""
            }
        conn.close()
        logger.info(f"載入 {len(portfolio)} 檔股票")
    except Exception as e:
        logger.error(f"無法讀取資料庫: {e}")
    return portfolio

def load_watchlist_from_db() -> List:
    """從 SQLite 載入觀察名單"""
    watchlist = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, industry, reason FROM watchlist")
        for row in cursor.fetchall():
            watchlist.append((row[0], row[1], row[2], row[3] or ""))
        conn.close()
        logger.info(f"載入 {len(watchlist)} 檔觀察名單")
    except Exception as e:
        logger.error(f"無法讀取觀察名單: {e}")
    return watchlist

# ==================== 初始化 ====================

PORTFOLIO = load_portfolio_from_db()
WATCH_LIST = load_watchlist_from_db()

MARKET_LEADERS = [
    ("2330", "台積電", "半導體", "AI/高效能運算"),
    ("2454", "聯發科", "IC設計", "AI/手機晶片"),
    ("2317", "鴻海", "電子", "AI伺服器/蘋果供應鏈"),
    ("2382", "廣達", "電子", "AI伺服器"),
    ("3711", "日月光", "半導體", "AI先進封裝"),
    ("3231", "緯創", "電子", "AI伺服器"),
    ("3034", "聯詠", "IC設計", "AI/顯示驅動"),
    ("4952", "凌通", "IC設計", "AI/周邊晶片"),
]

ALL_STOCKS = list(PORTFOLIO.keys()) + [s[0] for s in WATCH_LIST] + [s[0] for s in MARKET_LEADERS]

# ==================== Telegram API ====================

def send_telegram_message(message: str, reply_markup: str = None) -> bool:
    """發送 Telegram 訊息"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("未設定 Telegram Bot Token 或 Chat ID")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        
        if reply_markup:
            data["reply_markup"] = reply_markup
        
        post_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=post_data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            if not result.get('ok'):
                logger.error(f"Telegram 錯誤: {result}")
            return result.get('ok', False)
    
    except Exception as e:
        logger.error(f"Telegram 發送失敗: {e}")
        return False

def answer_callback_query(callback_query_id: str, text: str = None, show_alert: bool = False):
    """回應 callback query"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
        data = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text
        if show_alert:
            data["show_alert"] = True
        
        post_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=post_data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning(f"Answer callback failed: {e}")

def edit_message_text(chat_id: str, message_id: int, text: str, reply_markup: str = None):
    """編輯訊息"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
        data = {"chat_id": chat_id, "message_id": message_id, "text": text}
        
        if reply_markup:
            data["reply_markup"] = reply_markup
        
        post_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=post_data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning(f"Edit message failed: {e}")

def get_callback_updates(offset: int = None) -> List:
    """取得 updates (polling)"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        if offset:
            url += f"?offset={offset}"
        
        text = fetch_url(url)
        if text:
            data = json.loads(text)
            if data.get('ok'):
                return data.get('result', [])
    except Exception as e:
        logger.warning(f"Get updates failed: {e}")
    return []

# ==================== 數據獲取 ====================

def get_market_index() -> Dict:
    """取得大盤指數"""
    result = {'taiex': None, 'taiex_pct': None, 'otc': None, 'otc_pct': None}
    
    # 台股加權
    url = "https://tw.quote.finance.yahoo.net/quote/chart?symbol=TAIEX&interval=d"
    text = fetch_url(url)
    if text:
        try:
            data = json.loads(text)
            meta = data.get('chart', {}).get('meta', {})
            result['taiex'] = meta.get('previousClose') or meta.get('regularMarketPrice')
        except:
            pass
    
    # OTC
    url = "https://tw.quote.finance.yahoo.net/quote/chart?symbol=OTC&interval=d"
    text = fetch_url(url)
    if text:
        try:
            data = json.loads(text)
            meta = data.get('chart', {}).get('meta', {})
            result['otc'] = meta.get('previousClose') or meta.get('regularMarketPrice')
        except:
            pass
    
    return result

def get_yahoo_quote(stock_id: str) -> Optional[Dict]:
    """從 Yahoo Finance 取得報價"""
    # 嘗試快取
    cached = load_cache(f"quote_{stock_id}")
    if cached:
        return cached
    
    # 台股
    url = f"https://tw.quote.finance.yahoo.net/quote/chart?symbol={stock_id}&interval=d"
    text = fetch_url(url)
    
    if not text:
        # 美股
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_id}?interval=1d&range=5d"
        text = fetch_url(url)
    
    if text:
        try:
            data = json.loads(text)
            
            # Yahoo Finance 新格式
            if 'chart' in data:
                result = data['chart']['result']
                if result:
                    meta = result[0].get('meta', {})
                    quote = {
                        'name': meta.get('shortName') or stock_id,
                        'price': meta.get('regularMarketPrice'),
                        'change': meta.get('regularMarketChange'),
                        'change_pct': meta.get('regularMarketChangePercent'),
                        'high': meta.get('regularMarketDayHigh'),
                        'low': meta.get('regularMarketDayLow'),
                        'volume': meta.get('regularMarketVolume'),
                    }
                    save_cache(f"quote_{stock_id}", quote)
                    return quote
                    
        except Exception as e:
            logger.warning(f"解析 {stock_id} 失敗: {e}")
    
    return None

def get_stock_prices_batch(stock_ids: List[str]) -> Dict[str, Dict]:
    """批量取得報價"""
    result = {}
    for stock_id in stock_ids:
        quote = get_yahoo_quote(stock_id)
        if quote:
            result[stock_id] = quote
        time.sleep(0.2)  # 避免請求过快
    return result

# ==================== 技術分析 ====================

def calculate_ma(prices: list, days: int) -> Optional[float]:
    """計算均線"""
    if len(prices) >= days:
        return sum(prices[-days:]) / days
    return None

def calculate_kd(prices: list, n: int = 9) -> Optional[Dict]:
    """計算 KD 值"""
    if len(prices) < n + 1:
        return None
    
    rsv = []
    for i in range(n, len(prices)):
        low_n = min(prices[i-n:i+1])
        high_n = max(prices[i-n:i+1])
        if high_n != low_n:
            rsv.append((prices[i] - low_n) / (high_n - low_n) * 100)
        else:
            rsv.append(50)
    
    if len(rsv) < 3:
        return None
    
    k = 50
    d = 50
    for r in rsv:
        k = (2/3) * k + (1/3) * r
        d = (2/3) * d + (1/3) * k
    
    return {'k': k, 'd': d}

def get_technical_indicators(stock_id: str, price_data: Dict) -> Optional[Dict]:
    """技術指標"""
    # 簡化版
    return None

def get_strategy(code: str, price: float, change_pct: float, tech: Optional[Dict], fund: Optional[Dict]) -> str:
    """判斷策略"""
    if change_pct > 5:
        return "🚀 強勢上漲"
    elif change_pct > 2:
        return "📈 持續看好"
    elif change_pct > 0:
        return "✅ 穩健成長"
    elif change_pct > -2:
        return "⚠️ 留意觀察"
    elif change_pct > -5:
        return "📉 回調注意"
    else:
        return "🛑 跌破支撐"

# ==================== 報告生成 ====================

def generate_keyboard(portfolio_list: list) -> str:
    """生成鍵盤"""
    buttons = []
    for i in range(0, len(portfolio_list), 2):
        row = []
        if i < len(portfolio_list):
            row.append({"text": portfolio_list[i], "callback_data": f"stock_{portfolio_list[i]}"})
        if i + 1 < len(portfolio_list):
            row.append({"text": portfolio_list[i+1], "callback_data": f"stock_{portfolio_list[i+1]}"})
        if row:
            buttons.append(row)
    
    return json.dumps({"inline_keyboard": buttons})

def get_stock_detail(code: str) -> str:
    """取得股票詳細資訊（合併版）"""
    if code not in PORTFOLIO:
        return f"❌ {code} 不在持股中"
    
    stock = PORTFOLIO[code]
    quote = get_yahoo_quote(code)
    
    if not quote:
        return f"❌ 無法取得 {code} 報價"
    
    price = quote.get('price', 0)
    change = quote.get('change_pct', 0)
    
    if price and stock.get('cost'):
        profit = (price - stock['cost']) / stock['cost'] * 100
        profit_amt = (price - stock['cost']) * stock.get('shares', 1000)
    else:
        profit = 0
        profit_amt = 0
    
    message = f"""
📊 {stock['name']} ({code})
━━━━━━━━━━━━━
💰 現價: {price}
📈 漲跌: {change:+.2f}%
📋 成本: {stock['cost']}
📦 股數: {stock.get('shares', 1000)}
━━━━━━━━━━━━━
💵 損益: {profit:+.2f}% ({profit_amt:+,.0f})
🎯 產業: {stock.get('industry', '-')}
📝 應用: {stock.get('application', '-')}
"""
    return message.strip()

def generate_report(sort_by: str = "profit", use_telegram: bool = False, with_keyboard: bool = True) -> str:
    """生成報告"""
    prices = get_stock_prices_batch(ALL_STOCKS)
    
    portfolio_data = []
    for code, stock in PORTFOLIO.items():
        if code in prices:
            quote = prices[code]
            price = quote.get('price', 0)
            change = quote.get('change_pct', 0)
            
            if price and stock.get('cost'):
                profit = (price - stock['cost']) / stock['cost'] * 100
                profit_amt = (price - stock['cost']) * stock.get('shares', 1000)
            else:
                profit = 0
                profit_amt = 0
            
            portfolio_data.append({
                'code': code,
                'name': stock['name'],
                'price': price,
                'change': change,
                'profit': profit,
                'profit_amt': profit_amt,
                'industry': stock.get('industry', '')
            })
    
    # 排序
    if sort_by == "up":
        portfolio_data.sort(key=lambda x: x['change'], reverse=True)
    elif sort_by == "down":
        portfolio_data.sort(key=lambda x: x['change'])
    else:
        portfolio_data.sort(key=lambda x: x['profit'], reverse=True)
    
    # 生成訊息
    market = get_market_index()
    message = f"📈 台股監控 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    
    if market.get('taiex'):
        message += f"大盤: {market['taiex']:,.0f}\n"
    
    message += "\n📊 持股表現：\n"
    
    for item in portfolio_data:
        emoji = "🚀" if item['profit'] > 5 else "📈" if item['profit'] > 0 else "📉"
        message += f"{emoji} {item['code']} {item['name'][:6]}\n"
        message += f"   {item['price']:,.0f} ({item['change']:+.1f}%)\n"
        message += f"   損益: {item['profit']:+.1f}%\n\n"
    
    if use_telegram:
        keyboard = generate_keyboard(list(PORTFOLIO.keys())) if with_keyboard else None
        send_telegram_message(message, keyboard)
    
    return message

def poll_callbacks():
    """輪詢回調"""
    logger.info("開始輪詢回調...")
    offset = None
    
    while True:
        updates = get_callback_updates(offset)
        
        for update in updates:
            offset = update['update_id'] + 1
            
            if 'callback_query' in update:
                query = update['callback_query']
                data = query.get('data', '')
                user = query.get('from', {}).get('first_name', 'User')
                
                answer_callback_query(query['id'], f"收到！")
                
                if data.startswith('stock_'):
                    code = data.split('_')[1]
                    detail = get_stock_detail(code)
                    edit_message_text(
                        query['message']['chat']['id'],
                        query['message']['message_id'],
                        detail
                    )
        
        time.sleep(2)

def main():
    """主函數"""
    import argparse
    parser = argparse.ArgumentParser(description='股票監控系統 v2.0')
    parser.add_argument('--no-cache', action='store_true', help='強制取得最新資料')
    parser.add_argument('--telegram', '-t', action='store_true', help='發送到 Telegram')
    parser.add_argument('--poll', action='store_true', help='持續監聽按鈕')
    parser.add_argument('--sort', choices=['up', 'down', 'profit'], default='profit', help='排序方式')
    args = parser.parse_args()
    
    if args.no_cache and os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        logger.info("快取已清除")
    
    if args.poll:
        poll_callbacks()
    else:
        generate_report(sort_by=args.sort, use_telegram=args.telegram)

if __name__ == "__main__":
    main()
