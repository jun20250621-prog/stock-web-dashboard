#!/usr/bin/env python3
"""
股票監控與分析系統 - v1.17
新增功能：
- Inline Keyboard 按鈕（點擊持股顯示詳細資訊）
- Callback Query 處理程式
"""

import urllib.request
import json
import time
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# ==================== 設定區 ====================

# 持股（產業別 / 應用）
PORTFOLIO = {
    "2331": {"cost": 27.4, "name": "精英", "stop_loss": 24, "stop_profit": 35},
    "5392": {"cost": 52.6, "name": "能率", "stop_loss": 47, "stop_profit": 65},
    "3287": {"cost": 29.90, "name": "廣寰科", "stop_loss": 25.5, "stop_profit": 39},
    "2317": {"cost": 224.0, "name": "鴻海"},
    "00687B": {"cost": 29.35, "name": "國泰20年美債"},
    "1773": {"cost": 147.0, "name": "勝一"},
}

# 觀察名單（產業別 / 應用）
WATCH_LIST = [
    ("2543", "皇昌", "營建", "低檔黃金交叉"),
    ("3380", "明泰", "電子", "低檔黃金交叉"),
    ("2049", "上銀", "機械", "中檔黃金交叉"),
    ("6425", "易發", "電子", "低檔中性"),
    ("2485", "兆赫", "電子", "高檔黃金交叉"),
    ("6443", "元晶", "電子", "高檔中性"),
]

# 大盤強勢股名單（可自訂追蹤）
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

CACHE_FILE = "/tmp/stock_cache_v117.json"
CACHE_TIMEOUT = 300

# Telegram 設定
TELEGRAM_BOT_TOKEN = "8294937993:AAFOY_rwU33p6ndhFrnDyjKFrSQ-_1KavOE"
TELEGRAM_CHAT_ID = "8137433836"

# iTick API 設定
ITICK_API_KEY = "ae7824e15cc34160bfe303310973ea9a77ee3c6b1c314202b2ff1bd23db02729"
ITICK_BASE_URL = "https://api.itick.org"

# ==================== 工具函數 ====================

def fetch_url(url: str, retries: int = 3) -> Optional[str]:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return None
    return None

def get_date_range(days: int = 30) -> tuple:
    taiwan_tz = timezone(timedelta(hours=8))
    today = datetime.now(taiwan_tz).date()
    start_date = (today - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    return start_date, end_date

# ==================== Telegram API ====================

def send_telegram_message(message: str, reply_markup: str = None) -> bool:
    """發送 Telegram 訊息"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ 未設定 Telegram Bot Token 或 Chat ID")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        
        if reply_markup:
            data["reply_markup"] = reply_markup
        
        post_data = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=post_data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            if not result.get('ok'):
                print(f"❌ Telegram 錯誤: {result}")
            return result.get('ok', False)
    
    except Exception as e:
        print(f"⚠️ Telegram 發送失敗: {e}")
        return False

def answer_callback_query(callback_query_id: str, text: str = None, show_alert: bool = False):
    """回應 callback query"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
        data = {
            "callback_query_id": callback_query_id
        }
        if text:
            data["text"] = text
        if show_alert:
            data["show_alert"] = True
        
        post_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=post_data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"⚠️ Answer callback failed: {e}")

def edit_message_text(chat_id: str, message_id: int, text: str, reply_markup: str = None):
    """編輯訊息"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text
        }
        
        if reply_markup:
            data["reply_markup"] = reply_markup
        
        post_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=post_data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"⚠️ Edit message failed: {e}")

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
        print(f"⚠️ Get updates failed: {e}")
    return []

# ==================== 數據獲取 ====================

def get_market_index() -> Dict:
    """取得大盤指數"""
    result = {'taiex': None, 'taiex_pct': None, 'otc': None, 'otc_pct': None}
    
    taiwan_tz = timezone(timedelta(hours=8))
    today = datetime.now(taiwan_tz).date()
    date_str = today.strftime('%Y%m%d')
    
    try:
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_str}&response=json&type=ALL"
        text = fetch_url(url)
        if text:
            data = json.loads(text)
            if data.get('stat') == 'OK':
                tables = data.get('tables', [])
                for t in tables:
                    if '指數' in t.get('title', '') and '臺灣證券交易所' in t.get('title', ''):
                        for row in t.get('data', []):
                            if '加權' in row[0] and '報酬' not in row[0]:
                                taiex = row[1].replace(',', '')
                                try:
                                    result['taiex'] = str(int(float(taiex)))
                                    result['taiex_pct'] = row[3] + '%'
                                except:
                                    pass
                        break
    except Exception as e:
        pass
    
    try:
        start_date, end_date = get_date_range(7)
        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=TPEx&start_date={start_date}&end_date={end_date}"
        text = fetch_url(url)
        if text:
            data = json.loads(text)
            if data.get('data') and len(data['data']) > 0:
                latest = data['data'][-1]
                prev = data['data'][-2] if len(data['data']) >= 2 else latest
                close = latest.get('close', 0)
                prev_close = prev.get('close', 0)
                result['otc'] = f"{close:.2f}"
                if prev_close:
                    pct = (close - prev_close) / prev_close * 100
                    result['otc_pct'] = f"{pct:+.2f}%"
    except:
        pass
    
    return result

# ==================== iTick API ====================

def get_itick_quote(stock_id: str, retries: int = 3) -> Optional[Dict]:
    """使用 iTick API 取得股票報價"""
    # iTick 不支援 ETF
    if stock_id.startswith('00') or stock_id.endswith('B'):
        return None
    
    for attempt in range(retries):
        try:
            import urllib.parse
            url = f"{ITICK_BASE_URL}/stock/quote"
            params = urllib.parse.urlencode({"region": "TW", "code": stock_id})
            
            headers = {
                'accept': 'application/json',
                'token': ITICK_API_KEY
            }
            
            req = urllib.request.Request(f"{url}?{params}", headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                if data.get('code') == 0 and data.get('data'):
                    d = data['data']
                    return {
                        'price': d.get('p', 0),
                        'prev_price': d.get('ld', 0),
                        'change': d.get('ch', 0),
                        'change_pct': d.get('chp', 0),
                        'open': d.get('o', 0),
                        'high': d.get('h', 0),
                        'low': d.get('l', 0),
                        'volume': int(d.get('v', 0)) if d.get('v') else 0,
                        'timestamp': d.get('t', 0)
                    }
                elif 'Rate limit' in data.get('error_msg', '') or data.get('code') == 429:
                    # Rate limit - wait and retry
                    wait_time = (attempt + 1) * 3
                    print(f"    ⏳ Rate limit, 等待 {wait_time}s...")
                    time.sleep(wait_time)
                    continue
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = (attempt + 1) * 5
                print(f"    ⏳ HTTP 429, 等待 {wait_time}s...")
                time.sleep(wait_time)
                continue
            print(f"  ❌ iTick {stock_id}: HTTP {e.code}")
        except Exception as e:
            print(f"  ❌ iTick {stock_id}: {e}")
    return None

def get_stock_prices_batch(stock_ids: List[str]) -> Dict[str, Dict]:
    result = {}
    if not stock_ids:
        return result
    
    cache_key = "prices_" + ",".join(sorted(stock_ids))
    cached = load_cache(cache_key)
    if cached:
        print(f"📦 使用快取")
        return cached
    
    print(f"📡 取得股價中...")
    
    # 使用 iTick API
    for i, stock_id in enumerate(stock_ids):
        if i > 0:
            time.sleep(2.0)  # iTick 速率限制 - 2秒間隔
        
        data = get_itick_quote(stock_id)
        
        if data and data.get('price'):
            result[stock_id] = {
                'price': data['price'],
                'change_pct': data['change_pct'],
                'volume': data.get('volume', 0),
                'prev_price': data.get('prev_price'),
                'open': data.get('open'),
                'high': data.get('high'),
                'low': data.get('low'),
                'source': 'itick'
            }
            print(f"  ✅ {stock_id}: ${data['price']:.2f} ({data['change_pct']:+.2f}%)")
        else:
            print(f"  ❌ {stock_id}: 無法取得報價")
    
    if result:
        save_cache(cache_key, result)
    
    return result

# ==================== 技術指標 ====================

def calculate_ma(prices: list, days: int) -> Optional[float]:
    if len(prices) < days:
        return None
    return sum(prices[-days:]) / days

def calculate_kd(prices: list, n: int = 9) -> Optional[Dict]:
    if len(prices) < n:
        return None
    
    highs = [float(p.get('max', 0)) for p in prices[-n:]]
    lows = [float(p.get('min', 0)) for p in prices[-n:]]
    close = float(prices[-1].get('close', 0))
    
    if not highs or not lows:
        return None
    
    highest = max(highs)
    lowest = min(lows)
    
    if highest == lowest:
        return None
    
    rsv = (close - lowest) / (highest - lowest) * 100
    
    return {'k': rsv, 'd': rsv, 'j': 3 * rsv - 2 * rsv}

def get_technical_indicators(stock_id: str, price_data: Dict) -> Optional[Dict]:
    items = price_data.get('data')
    if not items or len(items) < 20:
        return None
    
    prices = [float(item.get('close', 0)) for item in items]
    
    ma5 = calculate_ma(prices, 5)
    ma20 = calculate_ma(prices, 20)
    ma50 = calculate_ma(prices, 50)
    kd = calculate_kd(items)
    
    current_price = prices[-1]
    
    return {
        'price': current_price,
        'ma5': ma5,
        'ma20': ma20,
        'ma50': ma50,
        'kd': kd,
        'above_ma5': current_price > ma5 if ma5 else False,
        'above_ma20': current_price > ma20 if ma20 else False,
        'above_ma50': current_price > ma50 if ma50 else False,
    }

# ==================== 選股策略 ====================

def get_strategy(code: str, price: float, change_pct: float, tech: Optional[Dict], fund: Optional[Dict]) -> str:
    if code in PORTFOLIO:
        stock = PORTFOLIO[code]
        cost = stock['cost']
        stop_loss = stock.get('stop_loss', cost * 0.9)
        stop_profit = stock.get('stop_profit', cost * 1.15)
        
        if price and cost:
            profit_pct = (price - cost) / cost * 100
            
            if price >= stop_profit:
                return "🔥 達標停利"
            elif price <= stop_loss:
                return "🛑 觸及停損"
            elif profit_pct > 15:
                return "✅ 續抱"
            elif profit_pct > 8:
                return "🔸 續抱等解套"
            elif profit_pct > 0:
                return "🔸 續抱等解套"
            elif profit_pct > -5:
                return "⚠️ 留意"
            else:
                return "🛑 建議停損"
    
    if tech and tech.get('kd'):
        k = tech['kd'].get('k', 0)
        d = tech['kd'].get('d', 0)
        
        if k > d and k < 30:
            return "🚀 KD黃金交叉"
        elif k < d and k > 70:
            return "💔 KD死亡交叉"
    
    if tech and tech.get('above_ma50'):
        return "📈 站上MA50"
    
    if change_pct:
        if change_pct > 7:
            return "⚠️ 漲多"
        elif change_pct > 3:
            return "📈 強勢"
        elif change_pct > 0:
            return "🔸 穩健"
        else:
            return "📉 觀望"
    
    return "🔸 觀察中"

# ==================== 快取 ====================

def load_cache(key: str) -> Optional[Dict]:
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
            if key in cache:
                cached_time = cache[key].get('_time', 0)
                if time.time() - cached_time < CACHE_TIMEOUT:
                    return cache[key].get('data', {})
    except:
        pass
    return None

def save_cache(key: str, data: Dict):
    try:
        cache = {}
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
        cache[key] = {'data': data, 'time': time.time()}
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except:
        pass

# ==================== 報告生成 ====================

def generate_keyboard(portfolio_list: list) -> str:
    """生成持股的 inline keyboard"""
    buttons = []
    for p in portfolio_list:
        code = p['code']
        name = p['name']
        price = p.get('price')
        change = p.get('change_pct', 0)
        
        if price:
            emoji = "🟢" if change >= 0 else "🔴"
            btn_text = f"{emoji} {name} ${price:.0f} {change:+.1f}%"
        else:
            btn_text = f"❓ {name}"
        
        # callback_data 格式: stock_代號
        buttons.append([{"text": btn_text, "callback_data": f"stock_{code}"}])
    
    keyboard = {
        "inline_keyboard": buttons
    }
    return json.dumps(keyboard)

def get_stock_detail(code: str) -> str:
    """取得股票詳細資訊"""
    if code not in PORTFOLIO:
        return f"❌ 無此持股: {code}"
    
    stock = PORTFOLIO[code]
    
    # 取得股價
    price_data = get_stock_prices_batch([code])
    data = price_data.get(code, {})
    price = data.get('price')
    change_pct = data.get('change_pct', 0)
    
    tech_data = get_technical_indicators(code, data)
    
    lines = []
    lines.append(f"📊 *{stock['name']} ({code})*")
    lines.append(f"🏷️ 產業: {stock['industry']} / {stock['application']}")
    lines.append("")
    lines.append(f"💰 成本: ${stock['cost']:.0f}")
    
    if price:
        profit = price - stock['cost']
        profit_pct = (profit / stock['cost']) * 100
        lines.append(f"💵 現價: ${price:.2f} ({change_pct:+.2f}%)")
        lines.append(f"📈 損益: ${profit:+.0f} ({profit_pct:+.1f}%)")
        lines.append(f"🎯 停損: ${stock.get('stop_loss', 'N/A')} | 停利: ${stock.get('stop_profit', 'N/A')}")
    else:
        lines.append("💵 現價: N/A")
    
    lines.append("")
    
    if tech_data:
        lines.append("📊 技術指標:")
        if tech_data.get('ma5'):
            lines.append(f"  MA5: ${tech_data['ma5']:.2f}")
        if tech_data.get('ma20'):
            lines.append(f"  MA20: ${tech_data['ma20']:.2f}")
        if tech_data.get('ma50'):
            lines.append(f"  MA50: ${tech_data['ma50']:.2f}")
        
        kd = tech_data.get('kd', {})
        if kd:
            lines.append(f"  K: {kd.get('k', 0):.1f} | D: {kd.get('d', 0):.1f}")
    
    lines.append("")
    lines.append(f"📝 策略: {get_strategy(code, price, change_pct, tech_data, None)}")
    
    return "\n".join(lines)

def generate_report(sort_by: str = "profit", use_telegram: bool = False, with_keyboard: bool = True) -> str:
    lines = []
    
    # Header
    lines.append("=" * 90)
    lines.append("📈 台股每日分析報告 v1.17")
    taiwan_tz = timezone(timedelta(hours=8))
    taiwan_time = datetime.now(taiwan_tz)
    lines.append(f"📅 日期：{taiwan_time.strftime('%Y/%m/%d %H:%M')}")
    lines.append("=" * 90)
    
    # 1. 大盤指數
    lines.append("\n【1️⃣ 大盤指數】")
    lines.append("-" * 50)
    
    idx = get_market_index()
    lines.append(f"  📊 櫃買指數：{idx['otc'] or 'N/A'}  ({idx['otc_pct'] or 'N/A'})")
    lines.append(f"  📊 台股加權(估)：{idx['taiex'] or 'N/A'}  ({idx['taiex_pct'] or 'N/A'})")
    
    # 2. 取得股價和技術指標
    price_data = get_stock_prices_batch(ALL_STOCKS)
    
    tech_data = {}
    
    print(f"📊 計算技術指標...")
    for stock_id in ALL_STOCKS:
        if stock_id in price_data:
            tech = get_technical_indicators(stock_id, price_data[stock_id])
            if tech:
                tech_data[stock_id] = tech
    
    # 3. 強勢股 TOP 3
    lines.append("\n【2️⃣ 強勢股 TOP 3】")
    lines.append("-" * 90)
    
    results = []
    for item in WATCH_LIST:
        stock_id, stock_name = item[0], item[1]
        data = price_data.get(stock_id, {})
        if data.get('change_pct'):
            results.append({
                'code': stock_id,
                'name': stock_name,
                'price': data.get('price'),
                'change_pct': data.get('change_pct'),
                'tech': tech_data.get(stock_id, {})
            })
    
    if sort_by == "up":
        results = sorted([r for r in results if r['change_pct'] and r['change_pct'] > 0], 
                       key=lambda x: x['change_pct'], reverse=True)
    elif sort_by == "down":
        results = sorted(results, key=lambda x: x['change_pct'] if x['change_pct'] else 999, reverse=False)
    else:
        results = sorted([r for r in results if r['change_pct'] and r['change_pct'] > 0], 
                       key=lambda x: x['change_pct'], reverse=True)
    
    lines.append(f"{'排名':<4} {'股名':<8} {'現價':<8} {'MA5':<8} {'MA20':<8} {'K':<8} {'漲跌幅':<8}")
    lines.append("-" * 90)
    for i, r in enumerate(results[:3], 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        tech = r.get('tech', {})
        price_str = f"${r['price']:.0f}" if r['price'] else "N/A"
        ma5_str = f"${tech.get('ma5', 0):.0f}" if tech.get('ma5') else "-"
        ma20_str = f"${tech.get('ma20', 0):.0f}" if tech.get('ma20') else "-"
        kd = tech.get('kd', {})
        k_str = f"{kd.get('k', 0):.1f}" if kd else "-"
        lines.append(f"{emoji}{i:<2}  {r['name']:<8} {price_str:<8} {ma5_str:<8} {ma20_str:<8} {k_str:<8} {r['change_pct']:+.2f}%")
    
    # 4. 大盤強勢股
    lines.append("\n【🚀 大盤強勢股】")
    lines.append("-" * 95)
    
    leader_results = []
    for item in MARKET_LEADERS:
        stock_id, stock_name = item[0], item[1]
        data = price_data.get(stock_id, {})
        if data.get('change_pct'):
            leader_results.append({
                'code': stock_id,
                'name': stock_name,
                'price': data.get('price'),
                'change_pct': data.get('change_pct'),
                'industry': item[2],
                'application': item[3],
            })
    
    leader_results = sorted(leader_results, key=lambda x: x['change_pct'] if x['change_pct'] else -999, reverse=True)
    
    limit_up = [r for r in leader_results if r['change_pct'] and r['change_pct'] >= 9]
    near_limit = [r for r in leader_results if r['change_pct'] and 5 <= r['change_pct'] < 9]
    strong = [r for r in leader_results if r['change_pct'] and 0 <= r['change_pct'] < 5]
    
    lines.append(f"{'股名':<10} {'產業':<10} {'現價':<8} {'漲跌幅':<10} {'評估'}")
    lines.append("-" * 95)
    
    if limit_up:
        for r in limit_up:
            change = r['change_pct']
            price_str = f"${r['price']:.0f}" if r['price'] else "N/A"
            lines.append(f"{r['name']:<10} {r['industry']:<10} {price_str:<8} {change:+.2f}%   🚀 漲停")
    
    if near_limit:
        for r in near_limit:
            change = r['change_pct']
            price_str = f"${r['price']:.0f}" if r['price'] else "N/A"
            lines.append(f"{r['name']:<10} {r['industry']:<10} {price_str:<8} {change:+.2f}%   🔥 接近漲停")
    
    for r in strong[:5]:
        change = r['change_pct']
        price_str = f"${r['price']:.0f}" if r['price'] else "N/A"
        lines.append(f"{r['name']:<10} {r['industry']:<10} {price_str:<8} {change:+.2f}%   📈 強勢")
    
    # 5. 持股狀況
    lines.append("\n【3️⃣ 持股狀況】")
    lines.append("-" * 120)
    lines.append(f"{'股名':<8} {'成本':<6} {'現價':<6} {'MA5':<6} {'MA20':<6} {'K':<6} {'停損':<6} {'停利':<6} {'損益':<12} {'漲跌幅':<8} {'策略'}")
    lines.append("-" * 120)
    
    portfolio_list = []
    for code, stock in PORTFOLIO.items():
        data = price_data.get(code, {})
        tech = tech_data.get(code, {})
        
        price = data.get('price')
        change_pct = data.get('change_pct')
        cost = stock['cost']
        
        kd = tech.get('kd', {}) if tech else {}
        
        strategy = get_strategy(code, price, change_pct, tech, None)
        
        if price:
            profit = price - cost
            profit_pct = (profit / cost) * 100
        else:
            profit = None
            profit_pct = None
        
        portfolio_list.append({
            'name': stock['name'],
            'code': code,
            'cost': cost,
            'price': price,
            'tech': tech,
            'kd': kd,
            'stop_loss': stock.get('stop_loss'),
            'stop_profit': stock.get('stop_profit'),
            'profit': profit,
            'profit_pct': profit_pct,
            'change_pct': change_pct,
            'strategy': strategy,
        })
    
    # 排序
    if sort_by == "up":
        portfolio_list = sorted(portfolio_list, key=lambda x: x['change_pct'] if x['change_pct'] else -999, reverse=True)
    elif sort_by == "down":
        portfolio_list = sorted(portfolio_list, key=lambda x: x['change_pct'] if x['change_pct'] else 999, reverse=False)
    else:
        portfolio_list.sort(key=lambda x: x['profit_pct'] if x['profit_pct'] else -999, reverse=True)
    
    for p in portfolio_list:
        tech = p.get('tech', {})
        kd = p.get('kd', {})
        
        cost_str = f"${p['cost']:.0f}"
        price_str = f"${p['price']:.0f}" if p['price'] else "N/A"
        ma5_str = f"${tech.get('ma5', 0):.0f}" if tech.get('ma5') else "-"
        ma20_str = f"${tech.get('ma20', 0):.0f}" if tech.get('ma20') else "-"
        k_str = f"{kd.get('k', 0):.1f}" if kd else "-"
        
        if p['profit'] is not None:
            profit_str = f"${p['profit']:+.0f} ({p['profit_pct']:+.1f}%)"
        else:
            profit_str = "-"
        
        change_str = f"{p['change_pct']:+.2f}%" if p['change_pct'] else "N/A"
        
        sl = str(p['stop_loss']) if p['stop_loss'] else '-'
        sp = str(p['stop_profit']) if p['stop_profit'] else '-'
        lines.append(f"{p['name']:<8} {cost_str:<6} {price_str:<6} {ma5_str:<6} {ma20_str:<6} {k_str:<6} ${sl:<5} ${sp:<5} {profit_str:<14} {change_str:<10} {p['strategy']}")
    
    # 6. 觀察名單
    lines.append("\n【4️⃣ 觀察名單】")
    lines.append("-" * 90)
    lines.append(f"{'股名':<10} {'現價':<8} {'MA5':<8} {'MA20':<8} {'K':<8} {'漲跌幅':<8} {'策略'}")
    lines.append("-" * 90)
    
    watch_list_sorted = []
    for item in WATCH_LIST:
        stock_id, stock_name = item[0], item[1]
        data = price_data.get(stock_id, {})
        tech = tech_data.get(stock_id, {})
        price = data.get('price')
        change_pct = data.get('change_pct')
        
        kd = tech.get('kd', {}) if tech else {}
        
        price_str = f"${price:.0f}" if price else "N/A"
        ma5_str = f"${tech.get('ma5', 0):.0f}" if tech.get('ma5') else "-"
        ma20_str = f"${tech.get('ma20', 0):.0f}" if tech.get('ma20') else "-"
        k_str = f"{kd.get('k', 0):.1f}" if kd else "-"
        change_str = f"{change_pct:+.2f}%" if change_pct else "N/A"
        
        strategy = get_strategy(stock_id, price, change_pct, tech, None)
        
        watch_list_sorted.append({
            'name': stock_name,
            'price': price_str,
            'ma5': ma5_str,
            'ma20': ma20_str,
            'k': k_str,
            'change': change_str,
            'strategy': strategy
        })
    
    if sort_by == "up":
        watch_list_sorted = sorted(watch_list_sorted, key=lambda x: float(x['change'].replace('%','').replace('+','')) if x['change'] != 'N/A' else -999, reverse=True)
    elif sort_by == "down":
        watch_list_sorted = sorted(watch_list_sorted, key=lambda x: float(x['change'].replace('%','').replace('+','')) if x['change'] != 'N/A' else 999, reverse=False)
    
    for w in watch_list_sorted:
        lines.append(f"{w['name']:<10} {w['price']:<8} {w['ma5']:<8} {w['ma20']:<8} {w['k']:<8} {w['change']:<8} {w['strategy']}")
    
    # Footer
    lines.append("\n" + "=" * 90)
    lines.append("✅ 點擊持股查看詳細資訊")
    lines.append("=" * 90)
    
    report = "\n".join(lines)
    
    # 生成 keyboard
    keyboard_str = None
    if with_keyboard:
        keyboard_str = generate_keyboard(portfolio_list)
    
    # Telegram 輸出（精簡格式 + keyboard）
    if use_telegram:
        tg_lines = []
        tg_lines.append("📈 *台股每日分析* v1.17")
        tg_lines.append(f"📅 {taiwan_time.strftime('%Y/%m/%d %H:%M')}")
        tg_lines.append("")
        
        # 大盤
        idx = get_market_index()
        taiex = idx.get('taiex', 'N/A')
        taiex_pct = idx.get('taiex_pct', 'N/A')
        otc = idx.get('otc', 'N/A')
        otc_pct = idx.get('otc_pct', 'N/A')
        tg_lines.append(f"🏢 大盤：加權 {taiex} ({taiex_pct}) | 櫃買 {otc} ({otc_pct})")
        
        # 持股（精簡版）
        tg_lines.append("")
        tg_lines.append("💼 *持股 (點擊查看詳情)*")
        
        portfolio_list_tg = []
        for code, stock in PORTFOLIO.items():
            data = price_data.get(code, {})
            price = data.get('price')
            change = data.get('change_pct', 0)
            cost = stock['cost']
            
            if price:
                profit = price - cost
                profit_pct = (profit / cost) * 100
                emoji = "🟢" if profit > 0 else "🔴"
                tg_lines.append(f"{emoji} {stock['name']}: ${price:.0f} ({change:+.1f}%) | 損益: {profit_pct:+.1f}%")
        
        tg_lines.append("")
        tg_lines.append("👀 *觀察*")
        
        for item in WATCH_LIST:
            stock_id, stock_name, industry, application = item[0], item[1], item[2], item[3]
            data = price_data.get(stock_id, {})
            price = data.get('price', 0)
            change = data.get('change_pct', 0)
            tg_lines.append(f"• {stock_name}: ${price:.0f} ({change:+.1f}%) | {industry}/{application}")
        
        # 大盤強勢股
        limit_up_tg = [(item, price_data.get(item[0], {})) for item in MARKET_LEADERS]
        limit_up_tg = [(item, data) for item, data in limit_up_tg if data.get('change_pct', 0) >= 9]
        near_limit_tg = [(item, data) for item, data in [(item, price_data.get(item[0], {})) for item in MARKET_LEADERS] if 5 <= data.get('change_pct', 0) < 9]
        
        if limit_up_tg or near_limit_tg:
            tg_lines.append("")
            tg_lines.append("🚀 *漲停股*")
            for item, data in limit_up_tg[:5]:
                stock_name = item[1]
                industry = item[2]
                price = data.get('price', 0)
                change = data.get('change_pct', 0)
                tg_lines.append(f"🚀 {stock_name}: ${price:.0f} ({change:+.1f}%) | {industry}")
            
            for item, data in near_limit_tg[:5]:
                stock_name = item[1]
                industry = item[2]
                price = data.get('price', 0)
                change = data.get('change_pct', 0)
                tg_lines.append(f"🔥 {stock_name}: ${price:.0f} ({change:+.1f}%) | {industry}")
        
        tg_lines.append("")
        tg_lines.append("✅ 點擊持股查看詳細資訊")
        
        tg_msg = "\n".join(tg_lines)
        
        # 發送訊息（包含 keyboard）
        print("📱 發送 Telegram 訊息...")
        result = send_telegram_message(tg_msg, keyboard_str)
        print(f"📱 Telegram 發送結果: {'✅ 成功' if result else '❌ 失敗'}")
    
    return report

def get_stock_detail(stock_id: str) -> str:
    """取得單一股票詳細資訊"""
    try:
        stock = PORTFOLIO.get(stock_id)
        if not stock:
            return f"❌ 無此持股: {stock_id}"
        
        # 取得股價
        price_data = get_stock_prices_batch([stock_id])
        data = price_data.get(stock_id, {})
        price = data.get('price', 0)
        change_pct = data.get('change_pct', 0)
        
        name = stock.get('name', stock_id)
        cost = stock.get('cost', 0)
        stop_loss = stock.get('stop_loss', 0)
        stop_profit = stock.get('stop_profit', 0)
        
        if price and cost:
            profit = price - cost
            profit_pct = (profit / cost) * 100
            emoji = "🟢" if profit > 0 else "🔴"
            info = f"""📊 *{name} ({stock_id}) 詳細資料*

💰 現價: ${price:.2f} ({change_pct:+.2f}%)
💵 成本: ${cost:.2f}
{emoji} 損益: ${profit:.2f} ({profit_pct:+.1f}%)"""
            
            if stop_loss:
                info += f"\n🛡️ 停損: ${stop_loss}"
            if stop_profit:
                info += f"\n🎯 停利: ${stop_profit}"
            
            # 簡單技術分析
            ma5 = data.get('ma5', 0)
            ma20 = data.get('ma20', 0)
            if ma5 and ma20:
                info += f"\n📈 MA5: ${ma5:.2f} | MA20: ${ma20:.2f}"
                if price > ma5 > ma20:
                    info += "\n✅ 短期均線多头排列"
                elif price < ma5 < ma20:
                    info += "\n⚠️ 短期均線空头排列"
            
            return info
        else:
            return f"📊 {name} ({stock_id})\n💵 成本: ${cost}"
    
    except Exception as e:
        return f"❌ 取得資料失敗: {e}"

def poll_callbacks():
    """持續監聽按鈕點擊"""
    print("🔄 開始監聽按鈕點擊...")
    print("按 Ctrl+C 停止")
    
    offset_file = "/tmp/stock_callback_offset.txt"
    
    # 讀取上次位置
    offset = None
    if os.path.exists(offset_file):
        try:
            with open(offset_file, 'r') as f:
                offset = int(f.read().strip())
                # 往前移一格確保不重複處理
                offset += 1
        except:
            offset = None
    
    while True:
        try:
            updates = get_callback_updates(offset)
            
            for update in updates:
                offset = update.get('update_id', 0)
                
                callback = update.get('callback_query')
                if not callback:
                    continue
                
                callback_id = callback.get('id')
                data = callback.get('data', '')
                message = callback.get('message', {})
                chat_id = message.get('chat', {}).get('id')
                message_id = message.get('message_id')
                
                # 解析 callback_data (格式: stock_代號)
                if data.startswith('stock_'):
                    stock_id = data.replace('stock_', '')
                    detail = get_stock_detail(stock_id)
                    
                    # 回應 callback (顯示 alert)
                    answer_callback_query(callback_id, detail, show_alert=True)
                    
                    # 也可以編輯訊息回覆
                    if chat_id and message_id:
                        edit_message_text(chat_id, message_id, detail)
                    
                    print(f"✅ 回應按鈕點擊: {stock_id}")
            
            # 儲存 offset
            if offset:
                try:
                    with open(offset_file, 'w') as f:
                        f.write(str(offset + 1))
                except:
                    pass
            
            time.sleep(2)
            
        except KeyboardInterrupt:
            print("\n🛑 停止監聽")
            break
        except Exception as e:
            print(f"⚠️ Polling 錯誤: {e}")
            time.sleep(5)

# ==================== 主程式 ====================

def main():
    use_cache = True
    use_telegram = False
    sort_by = "profit"
    poll_mode = False
    
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg == "--no-cache":
                use_cache = False
            elif arg == "--telegram" or arg == "-t":
                use_telegram = True
            elif arg == "--poll" or arg == "--listen":
                poll_mode = True
            elif arg == "--sort=up":
                sort_by = "up"
            elif arg == "--sort=down":
                sort_by = "down"
            elif arg == "--sort=profit":
                sort_by = "profit"
            elif arg == "--clear-cache":
                try:
                    os.remove(CACHE_FILE)
                    print("🗑️ 快取已清除")
                except:
                    pass
                return
            elif arg == "--help":
                print("""
股票監控系統 v1.17
用法: python stock_monitor_v7.py [選項]

選項:
  --no-cache        強制取得最新資料
  --telegram, -t   發送報告到 Telegram（含按鈕）
  --poll, --listen 持續監聽按鈕點擊
  --sort=up        按漲幅排序（漲最多在上）
  --sort=down      按跌幅排序（跌最多在上）
  --sort=profit     按損益排序（預設）
  --clear-cache    清除快取
  --help           顯示說明
                """)
                return
    
    if poll_mode:
        poll_callbacks()
        return
    
    report = generate_report(sort_by=sort_by, use_telegram=use_telegram)
    print(report)

if __name__ == "__main__":
    main()
