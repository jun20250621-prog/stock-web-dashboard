#!/usr/bin/env python3
"""
持股管理模組 - 使用 SQLite
Portfolio Manager with SQLite
"""

import sqlite3
import os
from typing import Dict, List, Optional
from datetime import datetime

class PortfolioManager:
    """持股管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        # 使用與 trade_journal 相同的資料庫
        self.db_path = config.get('database', {}).get('path', 'data/stock_data.db')
        # 確保路徑正確
        if not os.path.isabs(self.db_path):
            self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化資料庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT,
                cost REAL,
                shares INTEGER,
                stop_loss REAL,
                stop_profit REAL,
                industry TEXT,
                application TEXT,
                buy_date TEXT,
                -- 價格與損益（自動計算）
                current_price REAL,
                price_updated_at TEXT,
                profit_loss REAL,
                profit_loss_pct REAL,
                change_pct REAL,
                -- 技術指標
                ma5 REAL,
                ma20 REAL,
                ma60 REAL,
                rsi REAL,
                volume INTEGER,
                -- 基本面
                pe_ratio REAL,
                eps REAL,
                dividend_yield REAL,
                analyst_target REAL,
                -- 其他
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_all(self) -> Dict:
        """取得所有持股"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM portfolio")
        rows = cursor.fetchall()
        conn.close()
        
        portfolio = {}
        for row in rows:
            portfolio[row['code']] = {
                'id': row['id'],
                'code': row['code'],
                'name': row['name'],
                'cost': row['cost'],
                'shares': row['shares'],
                'stop_loss': row['stop_loss'],
                'stop_profit': row['stop_profit'],
                'industry': row['industry'],
                'application': row['application'],
                'buy_date': row['buy_date'],
                'current_price': row['current_price'],
                'price_updated_at': row['price_updated_at'],
                'profit_loss': row['profit_loss'],
                'profit_loss_pct': row['profit_loss_pct'],
                'change_pct': row['change_pct'],
                'ma5': row['ma5'],
                'ma20': row['ma20'],
                'ma60': row['ma60'],
                'rsi': row['rsi'],
                'volume': row['volume'],
                'pe_ratio': row['pe_ratio'],
                'eps': row['eps'],
                'dividend_yield': row['dividend_yield'],
                'analyst_target': row['analyst_target'],
                'notes': row['notes']
            }
        return portfolio
    
    def get(self, code: str) -> Optional[Dict]:
        """取得單一持股"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM portfolio WHERE code = ?", (code,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row['id'],
                'code': row['code'],
                'name': row['name'],
                'cost': row['cost'],
                'shares': row['shares'],
                'stop_loss': row['stop_loss'],
                'stop_profit': row['stop_profit'],
                'industry': row['industry'],
                'application': row['application'],
                'buy_date': row['buy_date'],
                'current_price': row['current_price'],
                'price_updated_at': row['price_updated_at'],
                'profit_loss': row['profit_loss'],
                'profit_loss_pct': row['profit_loss_pct'],
                'change_pct': row['change_pct'],
                'ma5': row['ma5'],
                'ma20': row['ma20'],
                'ma60': row['ma60'],
                'rsi': row['rsi'],
                'volume': row['volume'],
                'pe_ratio': row['pe_ratio'],
                'eps': row['eps'],
                'dividend_yield': row['dividend_yield'],
                'analyst_target': row['analyst_target'],
                'notes': row['notes']
            }
        return None
    
    def add(self, code: str, data: Dict) -> None:
        """新增持股"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO portfolio (
                code, name, cost, shares, stop_loss, stop_profit, 
                industry, application, buy_date,
                current_price, price_updated_at, profit_loss, profit_loss_pct, change_pct,
                ma5, ma20, ma60, rsi, volume,
                pe_ratio, eps, dividend_yield, analyst_target, notes,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (
            code,
            data.get('name', ''),
            data.get('cost', 0),
            data.get('shares', 1000),
            data.get('stop_loss'),
            data.get('stop_profit'),
            data.get('industry', ''),
            data.get('application', ''),
            data.get('buy_date', ''),
            data.get('current_price'),
            data.get('price_updated_at'),
            data.get('profit_loss'),
            data.get('profit_loss_pct'),
            data.get('change_pct'),
            data.get('ma5'),
            data.get('ma20'),
            data.get('ma60'),
            data.get('rsi'),
            data.get('volume'),
            data.get('pe_ratio'),
            data.get('eps'),
            data.get('dividend_yield'),
            data.get('analyst_target'),
            data.get('notes', ''),
        ))
        conn.commit()
        conn.close()
    
    def update(self, code: str, data: Dict) -> None:
        """更新持股"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE portfolio SET 
                name = ?, cost = ?, shares = ?, stop_loss = ?, stop_profit = ?,
                industry = ?, application = ?, buy_date = ?, updated_at = datetime('now')
            WHERE code = ?
        ''', (
            data.get('name', ''),
            data.get('cost', 0),
            data.get('shares', 1000),
            data.get('stop_loss'),
            data.get('stop_profit'),
            data.get('industry', ''),
            data.get('application', ''),
            data.get('buy_date', ''),
            code
        ))
        conn.commit()
        conn.close()
    
    def remove(self, code: str) -> None:
        """移除持股"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM portfolio WHERE code = ?", (code,))
        conn.commit()
        conn.close()
    
    def import_data(self, portfolio: Dict) -> None:
        """匯入持股資料"""
        for code, data in portfolio.items():
            self.add(code, data)
    
    def calculate_profit_loss(self, code: str, current_price: float) -> Dict:
        """計算損益"""
        stock = self.get(code)
        if not stock:
            return None
        
        cost = stock.get('cost', 0)
        shares = stock.get('shares', 0)
        
        cost_total = cost * shares
        current_total = current_price * shares
        profit_loss = current_total - cost_total
        profit_loss_pct = (profit_loss / cost_total * 100) if cost_total > 0 else 0
        
        return {
            'code': code,
            'name': stock.get('name'),
            'cost': cost,
            'shares': shares,
            'current_price': current_price,
            'cost_total': cost_total,
            'current_total': current_total,
            'profit_loss': profit_loss,
            'profit_loss_pct': profit_loss_pct,
            'stop_loss': stock.get('stop_loss'),
            'stop_profit': stock.get('stop_profit')
        }
    
    def check_alert(self, code: str, current_price: float, thresholds: Dict) -> Optional[Dict]:
        """檢查是否觸發警示"""
        pl = self.calculate_profit_loss(code, current_price)
        if not pl:
            return None
        
        profit_loss_pct = pl['profit_loss_pct']
        alerts = []
        
        if profit_loss_pct <= -thresholds.get('loss_threshold', 5):
            alerts.append('loss')
        
        if profit_loss_pct >= thresholds.get('gain_threshold', 10):
            alerts.append('gain')
        
        if alerts:
            return {
                'code': code,
                'name': pl['name'],
                'price': current_price,
                'profit_loss_pct': profit_loss_pct,
                'alerts': alerts
            }
        
        return None
    
    def update_price_and_analysis(self, code: str, price_data: Dict) -> None:
        """更新股價與分析資料"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 計算損益
        stock = self.get(code)
        if stock and price_data.get('current_price'):
            cost = stock.get('cost', 0)
            shares = stock.get('shares', 0)
            current_price = price_data.get('current_price')
            cost_total = cost * shares
            current_total = current_price * shares
            profit_loss = current_total - cost_total
            profit_loss_pct = (profit_loss / cost_total * 100) if cost_total > 0 else 0
        else:
            profit_loss = None
            profit_loss_pct = None
        
        cursor.execute('''
            UPDATE portfolio SET 
                current_price = ?,
                price_updated_at = ?,
                profit_loss = ?,
                profit_loss_pct = ?,
                change_pct = ?,
                ma5 = ?,
                ma20 = ?,
                ma60 = ?,
                rsi = ?,
                volume = ?,
                pe_ratio = ?,
                eps = ?,
                dividend_yield = ?,
                analyst_target = ?,
                notes = ?,
                updated_at = datetime('now')
            WHERE code = ?
        ''', (
            price_data.get('current_price'),
            price_data.get('price_updated_at'),
            profit_loss,
            profit_loss_pct,
            price_data.get('change_pct'),
            price_data.get('ma5'),
            price_data.get('ma20'),
            price_data.get('ma60'),
            price_data.get('rsi'),
            price_data.get('volume'),
            price_data.get('pe_ratio'),
            price_data.get('eps'),
            price_data.get('dividend_yield'),
            price_data.get('analyst_target'),
            price_data.get('notes', ''),
            code
        ))
        conn.commit()
        conn.close()
    
    def analyze_stock(self, code: str) -> Optional[Dict]:
        """分析單一股票"""
        stock = self.get(code)
        if not stock:
            return None
        
        # 計算建議
        profit_loss_pct = stock.get('profit_loss_pct', 0)
        stop_loss = stock.get('stop_loss')
        stop_profit = stock.get('stop_profit')
        
        # 根據條件給出建議
        if profit_loss_pct <= -10:
            recommendation = 'sell'
            reason = '跌幅過大，建議停損'
        elif stop_loss and profit_loss_pct <= ((stop_loss - stock.get('cost', 0)) / stock.get('cost', 1) * 100):
            recommendation = 'sell'
            reason = '觸及停損點'
        elif profit_loss_pct >= 15:
            recommendation = 'sell'
            reason = '已達目標價，可考慮停利'
        elif profit_loss_pct >= 5:
            recommendation = 'hold'
            reason = '持續觀望，達到初步目標'
        else:
            recommendation = 'hold'
            reason = '續抱，等待行情'
        
        return {
            'code': code,
            'name': stock.get('name'),
            'cost': stock.get('cost'),
            'shares': stock.get('shares'),
            'current_price': stock.get('current_price'),
            'profit_loss': stock.get('profit_loss'),
            'profit_loss_pct': profit_loss_pct,
            'change_pct': stock.get('change_pct'),
            'stop_loss': stop_loss,
            'stop_profit': stop_profit,
            'industry': stock.get('industry'),
            'application': stock.get('application'),
            'ma5': stock.get('ma5'),
            'ma20': stock.get('ma20'),
            'rsi': stock.get('rsi'),
            'volume': stock.get('volume'),
            'pe_ratio': stock.get('pe_ratio'),
            'eps': stock.get('eps'),
            'dividend_yield': stock.get('dividend_yield'),
            'analyst_target': stock.get('analyst_target'),
            'notes': stock.get('notes'),
            'recommendation': recommendation,
            'reason': reason
        }
    
    def update_analysis(self, code: str, fetcher) -> Optional[Dict]:
        """更新股票分析資料（從 API 獲取）"""
        try:
            # 取得現價
            price_data = fetcher.get_price(code)
            # 取得歷史資料（計算技術指標）
            hist_data = fetcher.get_historical(code, days=90)
            
            if not price_data:
                return None
            
            current_price = price_data.get('current_price') or price_data.get('close')
            if not current_price:
                return None
            
            # 取得漲跌幅
            change_pct = price_data.get('change_pct') or price_data.get('change')
            
            # 從歷史資料提取技術指標
            ma5 = hist_data.get('ma5') if hist_data else None
            ma20 = hist_data.get('ma20') if hist_data else None
            ma60 = hist_data.get('ma60') if hist_data else None
            rsi = hist_data.get('rsi') if hist_data else None
            volume = hist_data.get('volume') if hist_data else None
            
            # 計算損益
            stock = self.get(code)
            if stock:
                cost = stock.get('cost', 0)
                shares = stock.get('shares', 0)
                cost_total = cost * shares
                current_total = current_price * shares
                profit_loss = current_total - cost_total
                profit_loss_pct = (profit_loss / cost_total * 100) if cost_total > 0 else 0
            else:
                profit_loss = None
                profit_loss_pct = None
            
            # 更新資料庫
            price_update = {
                'current_price': current_price,
                'price_updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'profit_loss': profit_loss,
                'profit_loss_pct': profit_loss_pct,
                'change_pct': change_pct,
                'ma5': ma5,
                'ma20': ma20,
                'ma60': ma60,
                'rsi': rsi,
                'volume': volume,
                'pe_ratio': None,
                'eps': None,
                'dividend_yield': None,
                'analyst_target': None,
                'notes': ''
            }
            
            self.update_price_and_analysis(code, price_update)
            
            return {
                'code': code,
                'current_price': current_price,
                'change_pct': change_pct,
                'ma5': ma5,
                'ma20': ma20,
                'ma60': ma60,
                'rsi': rsi,
                'volume': volume,
                'profit_loss': profit_loss,
                'profit_loss_pct': profit_loss_pct
            }
        except Exception as e:
            print(f"更新 {code} 分析資料失敗: {e}")
            return None
    
    def update_all_analysis(self, fetcher) -> List[Dict]:
        """更新所有持股的分析資料"""
        portfolio = self.get_all()
        results = []
        for code in portfolio:
            result = self.update_analysis(code, fetcher)
            if result:
                results.append(result)
        return results
