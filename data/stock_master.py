#!/usr/bin/env python3
"""
股票主資料庫模組 - 自動抓取個股資料
Stock Master Database Module
"""

import sqlite3
import os
import json
import time
import urllib.request
from typing import Dict, List, Optional
from datetime import datetime

# 嘗試引入 requests，失敗則用 urllib
try:
    import requests
    HAS_REQUESTS = True
except:
    HAS_REQUESTS = False

class StockMaster:
    """股票主資料庫管理器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化 stocks_master 表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks_master (
                code TEXT PRIMARY KEY,
                name TEXT,
                industry TEXT,
                market TEXT,
                price REAL DEFAULT 0,
                change_pct REAL DEFAULT 0,
                pe REAL,
                eps REAL,
                nav REAL,
                pb REAL,
                high_52w REAL,
                low_52w REAL,
                volume REAL,
                dividend_yield REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def get(self, code: str) -> Optional[Dict]:
        """取得股票資料"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stocks_master WHERE code = ?", (code,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def save(self, data: Dict) -> None:
        """儲存股票資料"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO stocks_master 
            (code, name, industry, market, price, change_pct, pe, eps, nav, pb, 
             high_52w, low_52w, volume, dividend_yield, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (
            data.get('code'),
            data.get('name'),
            data.get('industry'),
            data.get('market'),
            data.get('price', 0),
            data.get('change_pct', 0),
            data.get('pe'),
            data.get('eps'),
            data.get('nav'),
            data.get('pb'),
            data.get('high_52w'),
            data.get('low_52w'),
            data.get('volume'),
            data.get('dividend_yield'),
        ))
        conn.commit()
        conn.close()
    
    def fetch_and_save(self, code: str) -> Optional[Dict]:
        """從網路抓取股票資料並儲存"""
        data = fetch_stock_info(code)
        if data:
            self.save(data)
        return data


def fetch_stock_info(code: str) -> Optional[Dict]:
    """從 Yahoo 股市抓取股票資訊"""
    
    # 判斷上市/上櫃
    if code.startswith('6'):
        symbol = f"{code}.TWO"  # 上櫃
        market = "上櫃"
    else:
        symbol = f"{code}.TW"  # 上市
        market = "上市"
    
    # Yahoo Finance API
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        if HAS_REQUESTS:
            resp = requests.get(url, headers=headers, timeout=10)
        else:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=10)
            resp_text = resp.read().decode('utf-8')
            resp = type('obj', (object,), {'json': lambda x=None: json.loads(resp_text), 'status_code': 200})()
        
        if hasattr(resp, 'status_code') and resp.status_code != 200:
            return None
            
        data = resp.json() if hasattr(resp, 'json') else json.loads(resp)
        
        # 解析 JSON
        result = data.get('chart', {}).get('result', [])
        if not result:
            return None
            
        meta = result[0].get('meta', {})
        quote = result[0].get('indicators', {}).get('quote', [{}])[0]
        
        # 基本資料
        price = meta.get('regularMarketPrice', 0)
        prev_close = meta.get('previousClose', 0)
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
        
        # 52週高低
        high_52w = meta.get('fiftyTwoWeekHigh', 0)
        low_52w = meta.get('fiftyTwoWeekLow', 0)
        
        # 成交量
        volume = meta.get('regularMarketVolume', 0)
        
        # 取得股票名稱 (從 symbol)
        name = meta.get('symbol', code)
        if '.' in name:
            name = name.split('.')[0]
        
        # 嘗試取得產業 (從 fullExchangeName 或其他欄位)
        industry = meta.get('instrumentType', '股票')
        
        # 計算 EPS, PE (使用近4季資料)
        eps = 0
        pe = meta.get('trailingPE', 0)
        
        # 如果沒有 PE，用股價/EPS 計算
        if not pe and eps:
            pe = price / eps if eps else 0
        
        # 取得股息殖利率
        dividend_yield = meta.get('dividendYield', 0)
        
        # 簡化名稱
        name = get_stock_name_from_web(code) or name
        
        result_data = {
            'code': code,
            'name': name,
            'industry': industry,
            'market': market,
            'price': price,
            'change_pct': round(change_pct, 2),
            'pe': round(pe, 2) if pe else None,
            'eps': round(eps, 2) if eps else None,
            'nav': None,  # Yahoo 沒直接提供
            'pb': None,
            'high_52w': high_52w,
            'low_52w': low_52w,
            'volume': volume,
            'dividend_yield': round(dividend_yield * 100, 2) if dividend_yield else None
        }
        
        time.sleep(0.5)  # 避免請求太快
        return result_data
        
    except Exception as e:
        print(f"Error fetching {code}: {e}")
        return None


def get_stock_name_from_web(code: str) -> Optional[str]:
    """從鉅亨網取得股票名稱"""
    try:
        url = f"https://www.cnyes.com/twstock/{code}"
        
        if HAS_REQUESTS:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        else:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=5)
            resp = resp.read().decode('utf-8')
            return None
        
        if resp.status_code == 200:
            text = resp.text
            # 找股票名稱
            import re
            m = re.search(r'<title>([^<]+)\([^)]+\)</title>', text)
            if m:
                title = m.group(1)
                # 格式: "驊宏資"
                return title.split('(')[0].strip()
    except:
        pass
    return None


def calculate_target_price(data: Dict) -> Dict:
    """
    計算目標價 - 常用策略
    """
    price = data.get('price', 0)
    eps = data.get('eps')
    nav = data.get('nav') or data.get('book_value')  # 每股淨值
    pe = data.get('pe')
    
    results = {}
    
    # 1. Graham 公式: 股價 = √(22.5 × EPS × 淨值)
    if eps and nav and eps > 0 and nav > 0:
        graham_price = (22.5 * eps * nav) ** 0.5
        results['graham'] = round(graham_price, 2)
    
    # 2. EPS 法: EPS × 15 (合理的本益比)
    if eps and eps > 0:
        eps_price = eps * 15
        results['eps_15'] = round(eps_price, 2)
        
        # 樂觀版 EPS × 20
        results['eps_20'] = round(eps * 20, 2)
        
        # 保守版 EPS × 10
        results['eps_10'] = round(eps * 10, 2)
    
    # 3. PEG 法: EPS 成長率 (需要歷史資料，這裡用簡化版)
    if eps and pe and pe > 0:
        peg_price = eps * 10  # PEG = 1 的合理價
        results['peg_1'] = round(peg_price, 2)
    
    # 4. 安全邊際價 (現價打8折)
    if price > 0:
        results['safe_80'] = round(price * 0.8, 2)
        results['safe_70'] = round(price * 0.7, 2)
    
    # 5. 殖利率法 (目標殖利率 5%)
    # 需要的話可實作
    
    # 6. 產業平均 PE 法
    # 需要的話可實作
    
    return results


# 測試
if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        code = sys.argv[1]
        print(f"抓取 {code} 資料...")
        
        data = fetch_stock_info(code)
        if data:
            print("\n基本資料:")
            print(f"  名稱: {data.get('name')}")
            print(f"  產業: {data.get('industry')}")
            print(f"  市場: {data.get('market')}")
            print(f"  現價: {data.get('price')}")
            print(f"  漲跌幅: {data.get('change_pct')}%")
            print(f"  本益比: {data.get('pe')}")
            print(f"  52W高: {data.get('high_52w')}")
            print(f"  52W低: {data.get('low_52w')}")
            
            print("\n目標價計算:")
            targets = calculate_target_price(data)
            for k, v in targets.items():
                print(f"  {k}: {v}")
        else:
            print("抓取失敗")
