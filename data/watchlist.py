#!/usr/bin/env python3
"""
觀察名單管理模組
Watchlist Manager
"""

import json
import os
from typing import Dict, List, Optional


class WatchlistManager:
    """觀察名單管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.config_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'stock_cli',
            'config.json'
        )
    
    def get_all(self) -> List[Dict]:
        """取得所有觀察名單"""
        return self.config.get('watchlist', [])
    
    def get(self, code: str) -> Optional[Dict]:
        """取得單一觀察名單"""
        watchlist = self.get_all()
        for item in watchlist:
            if item.get('code') == code:
                return item
        return None
    
    def add(self, data: Dict) -> None:
        """新增觀察名單"""
        watchlist = self.get_all()
        watchlist.append(data)
        self._save(watchlist)
    
    def remove(self, code: str) -> None:
        """移除觀察名單"""
        watchlist = self.get_all()
        watchlist = [item for item in watchlist if item.get('code') != code]
        self._save(watchlist)
    
    def update(self, code: str, data: Dict) -> None:
        """更新觀察名單"""
        watchlist = self.get_all()
        for i, item in enumerate(watchlist):
            if item.get('code') == code:
                watchlist[i].update(data)
                break
        self._save(watchlist)
    
    def import_data(self, watchlist: List[Dict]) -> None:
        """匯入觀察名單"""
        self._save(watchlist)
    
    def _save(self, watchlist: List[Dict]) -> None:
        """儲存至設定檔"""
        self.config['watchlist'] = watchlist
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
