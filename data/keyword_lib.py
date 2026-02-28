#!/usr/bin/env python3
"""
關鍵字詞庫管理模組
Keyword Library Manager

功能：
- 關鍵字自動關聯策略
- 學習機制
"""

import sqlite3
from typing import Dict, List, Optional
from collections import defaultdict


class KeywordLibrary:
    """關鍵字詞庫管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.db_path = config.get('database', {}).get('path', 'data/stock_data.db')
        
        # 初始化資料庫
        self._init_db()
        
        # 載入初始詞庫
        self._load_initial_keywords()
    
    def _init_db(self):
        """初始化資料庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
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
    
    def _load_initial_keywords(self):
        """載入初始關鍵字詞庫"""
        # 從 config 讀取策略的關鍵字
        strategies = self.config.get('strategies', {})
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for strategy_id, strategy_data in strategies.items():
            keywords = strategy_data.get('keywords', [])
            
            for keyword in keywords:
                # 檢查是否已存在
                cursor.execute('''
                    SELECT keyword FROM keyword_library 
                    WHERE strategy_id = ? AND keyword = ?
                ''', (strategy_id, keyword))
                
                if not cursor.fetchone():
                    cursor.execute('''
                        INSERT INTO keyword_library (strategy_id, keyword, weight)
                        VALUES (?, ?, 1.0)
                    ''', (strategy_id, keyword))
        
        conn.commit()
        conn.close()
    
    def add_keywords(self, strategy_id: str, keywords: List[str]) -> None:
        """新增關鍵字"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for keyword in keywords:
            cursor.execute('''
                INSERT OR REPLACE INTO keyword_library (strategy_id, keyword, weight, usage_count)
                VALUES (?, ?, 1.0, 0)
            ''', (strategy_id, keyword))
        
        conn.commit()
        conn.close()
    
    def remove_keyword(self, strategy_id: str, keyword: str) -> None:
        """移除關鍵字"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM keyword_library WHERE strategy_id = ? AND keyword = ?
        ''', (strategy_id, keyword))
        
        conn.commit()
        conn.close()
    
    def get_keywords(self, strategy_id: str) -> List[str]:
        """取得策略的關鍵字"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT keyword FROM keyword_library WHERE strategy_id = ?
        ''', (strategy_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
    
    def get_all_mappings(self) -> Dict[str, List[str]]:
        """取得所有關鍵字對應"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT strategy_id, keyword FROM keyword_library ORDER BY strategy_id
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        mapping = defaultdict(list)
        for strategy_id, keyword in rows:
            mapping[strategy_id].append(keyword)
        
        return dict(mapping)
    
    def suggest_strategy(self, text: str) -> List[Dict]:
        """根據文字建議策略"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 取得所有關鍵字
        cursor.execute('SELECT strategy_id, keyword, weight FROM keyword_library')
        rows = cursor.fetchall()
        
        conn.close()
        
        # 比對關鍵字
        matches = []
        text_lower = text.lower()
        
        for strategy_id, keyword, weight in rows:
            if keyword.lower() in text_lower:
                matches.append({
                    'strategy_id': strategy_id,
                    'keyword': keyword,
                    'weight': weight
                })
        
        # 按權重排序
        matches.sort(key=lambda x: x['weight'], reverse=True)
        
        # 取得策略名稱
        strategies = self.config.get('strategies', {})
        
        result = []
        for match in matches:
            sid = match['strategy_id']
            if sid in strategies:
                result.append({
                    'strategy_id': sid,
                    'strategy_name': strategies[sid].get('name'),
                    'keyword': match['keyword'],
                    'confidence': match['weight']
                })
        
        return result
    
    def learn(self, keyword: str, suggested: str, chosen: str) -> None:
        """學習使用者選擇"""
        if suggested == chosen:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 記錄學習
        cursor.execute('''
            INSERT INTO keyword_learning (keyword, suggested_strategy, user_choice, timestamp)
            VALUES (?, ?, ?, datetime('now'))
        ''', (keyword, suggested, chosen))
        
        # 更新權重（增加被選擇的策略權重）
        cursor.execute('''
            UPDATE keyword_library 
            SET weight = weight + 0.1, usage_count = usage_count + 1
            WHERE strategy_id = ? AND keyword = ?
        ''', (chosen, keyword))
        
        # 降低建議但未被選擇的權重
        cursor.execute('''
            UPDATE keyword_library 
            SET weight = MAX(0.1, weight - 0.05)
            WHERE strategy_id = ? AND keyword = ?
        ''', (suggested, keyword))
        
        conn.commit()
        conn.close()
