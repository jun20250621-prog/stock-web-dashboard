#!/usr/bin/env python3
"""
交易紀錄管理模組
Trade Journal Manager

包含：
- 交易紀錄 CRUD
- 紀律評分計算
- 績效分析
"""

import json
import os
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict


class TradeJournal:
    """交易紀錄管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.db_path = config.get('database', {}).get('path', 'data/stock_data.db')
        
        # 確保目錄存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 初始化資料庫
        self._init_db()
    
    def _init_db(self):
        """初始化資料庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 交易紀錄表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                code TEXT,
                name TEXT,
                type TEXT,
                buy_date TEXT,
                buy_price REAL,
                sell_date TEXT,
                sell_price REAL,
                shares INTEGER,
                total_cost REAL,
                total_revenue REAL,
                profit_loss REAL,
                profit_loss_pct REAL,
                holding_days INTEGER,
                annualized_return REAL,
                entry_strategy_id TEXT,
                entry_reason TEXT,
                entry_indicators TEXT,
                exit_strategy_id TEXT,
                exit_reason TEXT,
                exit_indicators TEXT,
                result TEXT,
                success_reason TEXT,
                failure_reason TEXT,
                improvement TEXT,
                discipline TEXT,
                discipline_score INTEGER,
                tags TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        # 關鍵字詞庫表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keyword_library (
                strategy_id TEXT,
                keyword TEXT,
                weight REAL DEFAULT 1.0,
                usage_count INTEGER DEFAULT 0,
                last_used TEXT,
                PRIMARY KEY (strategy_id, keyword)
            )
        ''')
        
        # 關鍵字學習記錄表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keyword_learning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT,
                suggested_strategy TEXT,
                user_choice TEXT,
                timestamp TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _generate_id(self) -> str:
        """產生交易ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM trades')
        count = cursor.fetchone()[0]
        
        conn.close()
        
        return f"TRD{str(count + 1).zfill(3)}"
    
    def add_trade(self, trade_data: Dict) -> str:
        """新增交易紀錄"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        trade_id = self._generate_id()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 計算損益
        if trade_data.get('buy_price') and trade_data.get('shares'):
            total_cost = trade_data['buy_price'] * trade_data['shares']
            trade_data['total_cost'] = total_cost
        
        if trade_data.get('sell_price') and trade_data.get('shares'):
            total_revenue = trade_data['sell_price'] * trade_data['shares']
            trade_data['total_revenue'] = total_revenue
            
            if trade_data.get('total_cost'):
                pl = total_revenue - trade_data['total_cost']
                pl_pct = (pl / trade_data['total_cost']) * 100
                trade_data['profit_loss'] = pl
                trade_data['profit_loss_pct'] = pl_pct
        
        # 計算持有天數
        if trade_data.get('buy_date') and trade_data.get('sell_date'):
            try:
                buy = datetime.strptime(trade_data['buy_date'], '%Y-%m-%d')
                sell = datetime.strptime(trade_data['sell_date'], '%Y-%m-%d')
                holding_days = (sell - buy).days
                trade_data['holding_days'] = holding_days
            except:
                pass
        
        # 插入資料
        cursor.execute('''
            INSERT INTO trades (
                id, code, name, type, buy_date, buy_price, sell_date, sell_price,
                shares, total_cost, total_revenue, profit_loss, profit_loss_pct,
                holding_days, annualized_return, entry_strategy_id, entry_reason,
                entry_indicators, exit_strategy_id, exit_reason, exit_indicators,
                result, success_reason, failure_reason, improvement, discipline,
                discipline_score, tags, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_id,
            trade_data.get('code'),
            trade_data.get('name'),
            trade_data.get('type'),
            trade_data.get('buy_date'),
            trade_data.get('buy_price'),
            trade_data.get('sell_date'),
            trade_data.get('sell_price'),
            trade_data.get('shares'),
            trade_data.get('total_cost'),
            trade_data.get('total_revenue'),
            trade_data.get('profit_loss'),
            trade_data.get('profit_loss_pct'),
            trade_data.get('holding_days'),
            trade_data.get('annualized_return'),
            trade_data.get('entry_strategy_id'),
            trade_data.get('entry_reason'),
            trade_data.get('entry_indicators'),
            trade_data.get('exit_strategy_id'),
            trade_data.get('exit_reason'),
            trade_data.get('exit_indicators'),
            trade_data.get('result'),
            trade_data.get('success_reason'),
            trade_data.get('failure_reason'),
            trade_data.get('improvement'),
            trade_data.get('discipline'),
            trade_data.get('discipline_score'),
            trade_data.get('tags'),
            trade_data.get('notes'),
            now,
            now
        ))
        
        conn.commit()
        conn.close()
        
        return trade_id
    
    def get_trades(self, filters: Dict = None) -> List[Dict]:
        """取得交易紀錄"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT * FROM trades WHERE 1=1'
        params = []
        
        if filters:
            if filters.get('code'):
                query += ' AND code = ?'
                params.append(filters['code'])
            
            if filters.get('year'):
                if filters.get('type') == '買入':
                    query += " AND buy_date LIKE ?"
                    params.append(f"{filters['year']}%")
                else:
                    query += " AND (buy_date LIKE ? OR sell_date LIKE ?)"
                    params.extend([f"{filters['year']}%", f"{filters['year']}%"])
            
            if filters.get('discipline'):
                query += ' AND discipline = ?'
                params.append(filters['discipline'])
            
            if filters.get('result'):
                query += ' AND result = ?'
                params.append(filters['result'])
        
        query += ' ORDER BY buy_date DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
    
    def analyze_performance(self, year: int = None) -> Dict:
        """分析交易表現"""
        filters = {}
        if year:
            filters['year'] = year
        
        trades = self.get_trades(filters)
        
        if not trades:
            return {
                'total_trades': 0,
                'success_count': 0,
                'failure_count': 0,
                'success_rate': 0,
                'total_profit_loss': 0,
                'avg_profit_loss_pct': 0
            }
        
        # 基本統計
        total = len(trades)
        success = len([t for t in trades if t.get('result') == '成功'])
        failure = len([t for t in trades if t.get('result') == '失敗'])
        
        total_pl = sum([t.get('profit_loss', 0) or 0 for t in trades if t.get('profit_loss')])
        avg_pl_pct = sum([t.get('profit_loss_pct', 0) or 0 for t in trades if t.get('profit_loss_pct')]) / total if total > 0 else 0
        
        # 紀律分析
        discipline_analysis = self._analyze_discipline(trades)
        
        # 策略分析
        strategy_analysis = self._analyze_strategy(trades)
        
        return {
            'total_trades': total,
            'success_count': success,
            'failure_count': failure,
            'success_rate': (success / total * 100) if total > 0 else 0,
            'total_profit_loss': total_pl,
            'avg_profit_loss_pct': avg_pl_pct,
            'discipline_analysis': discipline_analysis,
            'strategy_analysis': strategy_analysis
        }
    
    def _analyze_discipline(self, trades: List[Dict]) -> Dict:
        """分析紀律"""
        groups = defaultdict(list)
        
        for trade in trades:
            disc = trade.get('discipline', '未記錄')
            groups[disc].append(trade)
        
        result = {}
        
        for disc, trades_list in groups.items():
            if not trades_list:
                continue
            
            total = len(trades_list)
            success = len([t for t in trades_list if t.get('result') == '成功'])
            avg_pl = sum([t.get('profit_loss_pct', 0) or 0 for t in trades_list]) / total if total > 0 else 0
            
            result[disc] = {
                'count': total,
                'success_count': success,
                'success_rate': (success / total * 100) if total > 0 else 0,
                'avg_profit_loss_pct': avg_pl,
                'total_profit_loss': sum([t.get('profit_loss', 0) or 0 for t in trades_list])
            }
        
        return result
    
    def _analyze_strategy(self, trades: List[Dict]) -> Dict:
        """分析策略"""
        groups = defaultdict(list)
        
        for trade in trades:
            strategy_id = trade.get('entry_strategy_id', '未記錄')
            groups[strategy_id].append(trade)
        
        result = {}
        
        for strategy_id, trades_list in groups.items():
            if not trades_list:
                continue
            
            total = len(trades_list)
            success = len([t for t in trades_list if t.get('result') == '成功'])
            avg_pl = sum([t.get('profit_loss_pct', 0) or 0 for t in trades_list]) / total if total > 0 else 0
            
            result[strategy_id] = {
                'count': total,
                'success_count': success,
                'success_rate': (success / total * 100) if total > 0 else 0,
                'avg_profit_loss_pct': avg_pl,
                'total_profit_loss': sum([t.get('profit_loss', 0) or 0 for t in trades_list])
            }
        
        return result
    
    def import_trades(self, trades: List[Dict], mode: str = 'merge') -> None:
        """匯入交易紀錄"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if mode == 'replace':
            cursor.execute('DELETE FROM trades')
        
        for trade in trades:
            trade_id = trade.get('id') or self._generate_id()
            
            # 檢查是否存在
            cursor.execute('SELECT id FROM trades WHERE id = ?', (trade_id,))
            exists = cursor.fetchone()
            
            if exists and mode == 'merge':
                # 更新
                cursor.execute('''
                    UPDATE trades SET
                        code = ?, name = ?, type = ?, buy_date = ?, buy_price = ?,
                        sell_date = ?, sell_price = ?, shares = ?, total_cost = ?,
                        total_revenue = ?, profit_loss = ?, profit_loss_pct = ?,
                        holding_days = ?, annualized_return = ?, entry_strategy_id = ?,
                        entry_reason = ?, entry_indicators = ?, exit_strategy_id = ?,
                        exit_reason = ?, exit_indicators = ?, result = ?, success_reason = ?,
                        failure_reason = ?, improvement = ?, discipline = ?,
                        discipline_score = ?, tags = ?, notes = ?, updated_at = ?
                    WHERE id = ?
                ''', (
                    trade.get('code'), trade.get('name'), trade.get('type'),
                    trade.get('buy_date'), trade.get('buy_price'), trade.get('sell_date'),
                    trade.get('sell_price'), trade.get('shares'), trade.get('total_cost'),
                    trade.get('total_revenue'), trade.get('profit_loss'), trade.get('profit_loss_pct'),
                    trade.get('holding_days'), trade.get('annualized_return'), trade.get('entry_strategy_id'),
                    trade.get('entry_reason'), trade.get('entry_indicators'), trade.get('exit_strategy_id'),
                    trade.get('exit_reason'), trade.get('exit_indicators'), trade.get('result'),
                    trade.get('success_reason'), trade.get('failure_reason'), trade.get('improvement'),
                    trade.get('discipline'), trade.get('discipline_score'), trade.get('tags'),
                    trade.get('notes'), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), trade_id
                ))
            else:
                # 新增
                self.add_trade(trade)
        
        conn.commit()
        conn.close()
    
    def backup(self) -> str:
        """備份資料庫"""
        import shutil
        
        backup_dir = os.path.join(os.path.dirname(self.db_path), 'backup')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'stock_data_{timestamp}.db')
        
        shutil.copy2(self.db_path, backup_path)
        
        return backup_path
