#!/usr/bin/env python3
"""
觀察名單管理模組 - 使用 SQLite
Watchlist Manager with SQLite
"""

import sqlite3
import os
from typing import Dict, List, Optional
from datetime import datetime

class WatchlistManager:
    """觀察名單管理器"""
    
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
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT,
                target_price REAL,
                reason TEXT,
                industry TEXT,
                add_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_all(self) -> List[Dict]:
        """取得所有觀察名單"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM watchlist")
        rows = cursor.fetchall()
        conn.close()
        
        watchlist = []
        for row in rows:
            watchlist.append({
                'id': row['id'],
                'code': row['code'],
                'name': row['name'],
                'target_price': row['target_price'],
                'reason': row['reason'],
                'industry': row['industry'],
                'add_date': row['add_date']
            })
        return watchlist
    
    def get(self, code: str) -> Optional[Dict]:
        """取得單一觀察名單"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM watchlist WHERE code = ?", (code,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row['id'],
                'code': row['code'],
                'name': row['name'],
                'target_price': row['target_price'],
                'reason': row['reason'],
                'industry': row['industry'],
                'add_date': row['add_date']
            }
        return None
    
    def add(self, data: Dict) -> None:
        """新增觀察名單"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO watchlist (code, name, target_price, reason, industry, add_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (
            data.get('code', ''),
            data.get('name', ''),
            data.get('target_price'),
            data.get('reason', ''),
            data.get('industry', ''),
            data.get('add_date', datetime.now().strftime('%Y-%m-%d'))
        ))
        conn.commit()
        conn.close()
    
    def remove(self, code: str) -> None:
        """移除觀察名單"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE code = ?", (code,))
        conn.commit()
        conn.close()
    
    def update(self, code: str, data: Dict) -> None:
        """更新觀察名單"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE watchlist SET 
                name = ?, target_price = ?, reason = ?, industry = ?, add_date = ?, updated_at = datetime('now')
            WHERE code = ?
        ''', (
            data.get('name', ''),
            data.get('target_price'),
            data.get('reason', ''),
            data.get('industry', ''),
            data.get('add_date', ''),
            code
        ))
        conn.commit()
        conn.close()
    
    def import_data(self, watchlist: List[Dict]) -> None:
        """匯入觀察名單"""
        for item in watchlist:
            self.add(item)
