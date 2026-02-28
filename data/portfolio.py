#!/usr/bin/env python3
"""
持股管理模組
Portfolio Manager
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime


class PortfolioManager:
    """持股管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.portfolio_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'config.json'
        )
    
    def get_all(self) -> Dict:
        """取得所有持股"""
        return self.config.get('portfolio', {})
    
    def get(self, code: str) -> Optional[Dict]:
        """取得單一持股"""
        portfolio = self.get_all()
        return portfolio.get(code)
    
    def add(self, code: str, data: Dict) -> None:
        """新增持股"""
        portfolio = self.get_all()
        portfolio[code] = data
        self._save(portfolio)
    
    def update(self, code: str, data: Dict) -> None:
        """更新持股"""
        portfolio = self.get_all()
        if code in portfolio:
            portfolio[code].update(data)
            self._save(portfolio)
    
    def remove(self, code: str) -> None:
        """移除持股"""
        portfolio = self.get_all()
        if code in portfolio:
            del portfolio[code]
            self._save(portfolio)
    
    def import_data(self, portfolio: Dict) -> None:
        """匯入持股資料"""
        self._save(portfolio)
    
    def _save(self, portfolio: Dict) -> None:
        """儲存至設定檔"""
        self.config['portfolio'] = portfolio
        
        with open(self.portfolio_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
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
