#!/usr/bin/env python3
"""
策略庫管理模組
Strategy Library Manager
"""

import json
import os
import sqlite3
from typing import Dict, List, Optional


class StrategyLibrary:
    """策略庫管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.strategies_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'config.json'
        )
        self.db_path = config.get('database', {}).get('path', 'data/stock_data.db')
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化資料庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategies (
                id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                entry_condition TEXT,
                exit_condition TEXT,
                stop_loss REAL,
                stop_profit REAL,
                risk_level TEXT,
                scenario TEXT,
                keywords TEXT,
                create_date TEXT,
                update_date TEXT,
                notes TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_strategies(self) -> List[Dict]:
        """取得所有策略"""
        # 從 config 讀取
        strategies = self.config.get('strategies', {})
        
        # 轉換為列表格式
        result = []
        for sid, data in strategies.items():
            data['id'] = sid
            result.append(data)
        
        return result
    
    def get_strategy(self, strategy_id: str) -> Optional[Dict]:
        """取得單一策略"""
        strategies = self.config.get('strategies', {})
        
        if strategy_id in strategies:
            data = strategies[strategy_id]
            data['id'] = strategy_id
            return data
        
        return None
    
    def add_strategy(self, strategy_data: Dict) -> str:
        """新增策略"""
        strategies = self.config.get('strategies', {})
        
        # 產生新 ID
        existing_ids = [k for k in strategies.keys() if k.startswith('STG')]
        next_num = max([int(k.replace('STG', '')) for k in existing_ids] or [0]) + 1
        strategy_id = f"STG{str(next_num).zfill(3)}"
        
        strategies[strategy_id] = strategy_data
        
        # 儲存
        self.config['strategies'] = strategies
        with open(self.strategies_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        
        return strategy_id
    
    def update_strategy(self, strategy_id: str, strategy_data: Dict) -> None:
        """更新策略"""
        strategies = self.config.get('strategies', {})
        
        if strategy_id in strategies:
            strategies[strategy_id].update(strategy_data)
            
            self.config['strategies'] = strategies
            with open(self.strategies_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def import_strategies(self, strategies: List[Dict]) -> None:
        """匯入策略"""
        strategies_dict = self.config.get('strategies', {})
        
        for strategy in strategies:
            strategy_id = strategy.get('id')
            if strategy_id:
                strategies_dict[strategy_id] = strategy
        
        self.config['strategies'] = strategies_dict
        with open(self.strategies_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def analyze_performance(self, strategy_id: str = None) -> Dict:
        """分析策略表現"""
        # 這裡需要從 trade_journal 取得數據
        # 簡化版本
        return {
            'strategy_id': strategy_id,
            'total_trades': 0,
            'success_rate': 0,
            'avg_return': 0
        }
