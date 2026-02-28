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
                'buy_date': row['buy_date']
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
                'buy_date': row['buy_date']
            }
        return None
    
    def add(self, code: str, data: Dict) -> None:
        """新增持股"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO portfolio (code, name, cost, shares, stop_loss, stop_profit, industry, application, buy_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (
            code,
            data.get('name', ''),
            data.get('cost', 0),
            data.get('shares', 1000),
            data.get('stop_loss'),
            data.get('stop_profit'),
            data.get('industry', ''),
            data.get('application', ''),
            data.get('buy_date', '')
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
