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
                code TEXT NOT NULL,
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
        # 檢查並移除舊的唯一約束（如果存在的話）
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_code ON portfolio(code)")
        except:
            pass
        conn.commit()
        conn.close()
    
    def get_all(self) -> List[Dict]:
        """取得所有持股"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM portfolio ORDER BY id")
        rows = cursor.fetchall()
        conn.close()
        
        portfolio = []
        for row in rows:
            portfolio.append({
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
            })
        return portfolio
    
    def get_by_id(self, id: int) -> Optional[Dict]:
        """根據 ID 取得持股"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM portfolio WHERE id = ?", (id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
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
    
    def get(self, code: str) -> Optional[Dict]:
        """取得單一持股（兼容舊版）"""
        print(f"[DEBUG] get() called with code: {repr(code)}")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM portfolio WHERE code = ?", (code,))
        row = cursor.fetchone()
        conn.close()
        print(f"[DEBUG] get() query result: {row}")
        
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
    
    def add(self, code: str, data: Dict) -> int:
        """新增持股，返回新增的 ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO portfolio (
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
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return new_id
    
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
    
    def calculate_profit_loss_by_id(self, id: int, current_price: float) -> Dict:
        """根據 ID 計算損益"""
        stock = self.get_by_id(id)
        if not stock:
            return {'profit_loss': 0, 'profit_loss_pct': 0}
        
        cost = stock.get('cost', 0)
        shares = stock.get('shares', 0)
        
        cost_total = cost * shares
        current_total = current_price * shares
        profit_loss = current_total - cost_total
        profit_loss_pct = (profit_loss / cost_total * 100) if cost_total > 0 else 0
        
        return {
            'code': stock.get('code'),
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
        print(f"[DEBUG] update_price_and_analysis called for {code} with data: {price_data}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 確保 code 格式一致
        code = code.replace('.TW', '').replace('.TWO', '')
        
        # 計算損益 - 注意 current_price 可能是 0
        stock = self.get(code)
        print(f"[DEBUG] stock from DB: {stock}")
        
        current_price = price_data.get('current_price')
        
        if stock and current_price is not None and current_price > 0:
            cost = stock.get('cost', 0)
            shares = stock.get('shares', 0)
            current_price = price_data.get('current_price')
            cost_total = cost * shares
            current_total = current_price * shares
            profit_loss = current_total - cost_total
            profit_loss_pct = (profit_loss / cost_total * 100) if cost_total > 0 else 0
            print(f"[DEBUG] calculated: cost={cost}, shares={shares}, price={current_price}, PL={profit_loss}")
        else:
            profit_loss = None
            profit_loss_pct = None
            print(f"[DEBUG] stock or price is None: stock={stock}, current_price={price_data.get('current_price')}")
        
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
        
        # 計算建議（處理 None 值）
        profit_loss_pct = stock.get('profit_loss_pct') or 0
        stop_loss = stock.get('stop_loss')
        stop_profit = stock.get('stop_profit')
        cost = stock.get('cost') or 0
        
        # 根據條件給出建議
        if profit_loss_pct <= -10:
            recommendation = 'sell'
            reason = '跌幅過大，建議停損'
        elif stop_loss and cost > 0 and profit_loss_pct <= ((stop_loss - cost) / cost * 100):
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
    
    def update_analysis(self, code: str, fetcher, fugle=None) -> Optional[Dict]:
        """更新股票分析資料"""
        try:
            # 取得資料庫中的持股資料
            stock = self.get(code)
            if not stock:
                return None
            
            # 優先使用 API 資料，若失敗則使用資料庫現有資料
            current_price = stock.get('current_price') or 0
            change_pct = stock.get('change_pct') or 0
            
            # 嘗試從 API 取得最新股價
            try:
                price_data = fetcher.get_price(code)
                if price_data and price_data.get('current_price'):
                    current_price = price_data.get('current_price')
                    change_pct = price_data.get('change_pct', 0)
            except Exception as e:
                print(f"API 取得股價失敗: {e}")
            
            # 技術指標（需要 API，若無則為空）
            ma5 = None
            ma20 = None
            ma60 = None
            rsi = None
            volume = None
            
            # 計算損益
            cost = stock.get('cost') or 0
            shares = stock.get('shares') or 0
            
            if current_price and cost > 0:
                cost_total = cost * shares
                current_total = current_price * shares
                profit_loss = current_total - cost_total
                profit_loss_pct = (profit_loss / cost_total * 100) if cost_total > 0 else 0
            else:
                profit_loss = stock.get('profit_loss') or 0
                profit_loss_pct = stock.get('profit_loss_pct') or 0
            
            # 根據損益給出建議
            if profit_loss_pct <= -10:
                recommendation = 'sell'
                reason = '跌幅過大，建議停損'
            elif profit_loss_pct <= -5:
                recommendation = 'sell'
                reason = '接近停損點'
            elif profit_loss_pct >= 15:
                recommendation = 'sell'
                reason = '已達目標價，可考慮停利'
            elif profit_loss_pct >= 8:
                recommendation = 'hold'
                reason = '達到初步目標，續抱'
            else:
                recommendation = 'hold'
                reason = '續抱，等待行情'
            
            # 返回分析結果
            return {
                'code': code,
                'name': stock.get('name'),
                'cost': cost,
                'shares': shares,
                'current_price': current_price if current_price > 0 else stock.get('current_price'),
                'profit_loss': profit_loss,
                'profit_loss_pct': profit_loss_pct,
                'change_pct': change_pct,
                'stop_loss': stock.get('stop_loss'),
                'stop_profit': stock.get('stop_profit'),
                'industry': stock.get('industry'),
                'application': stock.get('application'),
                'ma5': ma5,
                'ma20': ma20,
                'rsi': rsi,
                'volume': volume,
                'pe_ratio': stock.get('pe_ratio'),
                'eps': stock.get('eps'),
                'dividend_yield': stock.get('dividend_yield'),
                'analyst_target': stock.get('analyst_target'),
                'notes': stock.get('notes'),
                'recommendation': recommendation,
                'reason': reason
            }
        except Exception as e:
            print(f"分析 {code} 失敗: {e}")
            return None
    
    def update_all_analysis(self, fetcher, fugle=None) -> List[Dict]:
        """更新所有持股的分析資料"""
        portfolio = self.get_all()
        results = []
        for code in portfolio:
            result = self.update_analysis(code, fetcher, fugle)
            if result:
                results.append(result)
        return results

    def calculate_stop_loss_profit(self, code: str) -> Optional[Dict]:
        """計算建議停損停利價"""
        stock = self.get(code)
        if not stock:
            return None
        
        cost = stock.get('cost', 0)
        current_price = stock.get('current_price', 0)
        
        if not cost or not current_price:
            return None
        
        # 使用簡單的百分比計算
        # 停損：-8% 到 -10%
        # 停利：+10% 到 +15%
        stop_loss = round(cost * 0.92, 2)  # 8% 停損
        stop_loss_aggressive = round(cost * 0.90, 2)  # 10% 停損
        
        stop_profit = round(cost * 1.10, 2)  # 10% 停利
        stop_profit_aggressive = round(cost * 1.15, 2)  # 15% 停利
        
        # 建議停損（根據風險承受度）
        suggested_stop_loss = stop_loss
        
        # 計算現在的報酬率
        profit_pct = (current_price - cost) / cost * 100
        
        return {
            'code': code,
            'name': stock.get('name'),
            'cost': cost,
            'current_price': current_price,
            'profit_pct': round(profit_pct, 2),
            'stop_loss_conservative': stop_loss_aggressive,  # 保守 -10%
            'stop_loss': stop_loss,  # 一般 -8%
            'stop_profit': stop_profit,  # 保守 +10%
            'stop_profit_aggressive': stop_profit_aggressive  # 積極 +15%
        }

    def migrate_remove_unique(self):
        """移除舊的 unique 約束"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 嘗試移除 UNIQUE 約束
            cursor.execute("DROP INDEX IF EXISTS idx_code")
        except:
            pass
        try:
            # 重建一般索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_code ON portfolio(code)")
        except:
            pass
        conn.commit()
        conn.close()

    def migrate_fix_unique(self):
        """修復資料庫：移除 UNIQUE 約束"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 嘗試刪除舊的 UNIQUE 索引
            cursor.execute("DROP INDEX IF EXISTS idx_code")
        except:
            pass
        try:
            # 建立新的非 UNIQUE 索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_code ON portfolio(code)")
        except:
            pass
        conn.commit()
        conn.close()
        
# 模組載入時自動執行遷移
try:
    _pm = PortfolioManager({})
    _pm.migrate_fix_unique()
except:
    pass
