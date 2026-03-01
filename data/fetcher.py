#!/usr/bin/env python3
"""
股票資料取得模組 - 智慧快取版
Stock Data Fetcher - Enhanced with Caching
"""

import yfinance as yf
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import time
import json
import os
import logging

logger = logging.getLogger(__name__)


class StockDataCache:
    """智慧型快取機制"""
    
    def __init__(self, cache_dir='stock_cache', cache_duration=3600):
        self.cache_dir = cache_dir
        self.cache_duration = cache_duration  # 預設1小時
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_path(self, symbol: str, period: str = '1mo') -> str:
        return f"{self.cache_dir}/{symbol}_{period}.json"
    
    def get_cached_data(self, symbol: str, period: str = '1mo') -> Optional[Dict]:
        """取得快取數據"""
        cache_file = self._get_cache_path(symbol, period)
        
        if os.path.exists(cache_file):
            try:
                file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
                if datetime.now() - file_time < timedelta(seconds=self.cache_duration):
                    with open(cache_file, 'r') as f:
                        return json.load(f)
            except Exception as e:
                logger.debug(f"讀取快取失敗: {e}")
        
        return None
    
    def save_cache(self, symbol: str, data: Dict, period: str = '1mo') -> None:
        """儲存快取"""
        cache_file = self._get_cache_path(symbol, period)
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.debug(f"儲存快取失敗: {e}")


class StockDataFetcher:
    """股票資料取得器 - 智慧重試 + 快取版"""
    
    def __init__(self, cache_timeout: int = 3600):
        self.cache = StockDataCache(cache_duration=cache_timeout)
        self.cache_timeout = cache_timeout
        self.request_count = 0
        self.last_request_time = 0
        
    def _rate_limit(self):
        """頻率限制：每分鐘最多 10 個請求"""
        current_time = time.time()
        
        # 每 6 秒一個請求
        if current_time - self.last_request_time < 0.6:
            time.sleep(0.6 - (current_time - self.last_request_time))
        
        self.last_request_time = time.time()
        self.request_count += 1
        
        # 每分鐘重置計數
        if self.request_count >= 10:
            time.sleep(6)
            self.request_count = 0
    
    def _fetch_with_retry(self, symbol: str, max_retries: int = 3) -> Optional[Dict]:
        """帶重試的獲取機制"""
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                # 檢查快取
                cached = self.cache.get_cached_data(symbol, '1mo')
                if cached:
                    logger.info(f"從快取取得 {symbol}")
                    return cached
                
                # 嘗試上市
                stock = yf.Ticker(f"{symbol}.TW")
                info = stock.info
                
                if not info or 'currentPrice' not in info:
                    # 嘗試上櫃
                    stock = yf.Ticker(f"{symbol}.TWO")
                    info = stock.info
                
                if info and 'currentPrice' in info:
                    data = {
                        'code': symbol,
                        'price': info.get('currentPrice', 0),
                        'change': info.get('regularMarketChange', 0),
                        'change_pct': info.get('regularMarketChangePercent', 0),
                        'volume': info.get('volume', 0),
                        'high': info.get('regularMarketDayHigh', 0),
                        'low': info.get('regularMarketDayLow', 0),
                        'open': info.get('regularMarketOpen', 0),
                        'prev_close': info.get('regularMarketPreviousClose', 0),
                        'timestamp': datetime.now().isoformat()
                    }
                    # 儲存快取
                    self.cache.save_cache(symbol, data, '1mo')
                    return data
                
            except Exception as e:
                error_msg = str(e)
                if '429' in error_msg or 'Too Many Requests' in error_msg:
                    # 被限流，等一下
                    wait_time = (attempt + 1) * 10
                    logger.warning(f"{symbol} 被限流，等待 {wait_time} 秒")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"取得 {symbol} 失敗: {e}")
                    
        return None
    
    def get_price(self, stock_code: str) -> Optional[Dict]:
        """取得即時股價"""
        return self._fetch_with_retry(stock_code)
    
    def get_historical(self, stock_code: str, days: int = 90) -> Optional[Dict]:
        """取得歷史資料"""
        cache_key = f"hist_{stock_code}_{days}"
        cached = self.cache.get_cached_data(cache_key, f'{days}d')
        
        if cached:
            return cached
        
        try:
            self._rate_limit()
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 嘗試上市
            stock = yf.Ticker(f"{stock_code}.TW")
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                # 嘗試上櫃
                stock = yf.Ticker(f"{stock_code}.TWO")
                hist = stock.history(start=start_date, end=end_date)
            
            if not hist.empty:
                # 計算技術指標
                data = self._calculate_indicators(hist)
                
                # 儲存快取
                self.cache.save_cache(cache_key, data, f'{days}d')
                return data
            
        except Exception as e:
            logger.error(f"取得 {stock_code} 歷史資料失敗: {e}")
        
        return None
    
    def _calculate_indicators(self, df) -> Dict:
        """計算技術指標"""
        import pandas as pd
        import numpy as np
        
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        # MA
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        
        # KD指標
        low_min = low.rolling(9).min()
        high_max = high.rolling(9).max()
        
        # 避免除零
        diff = high_max - low_min
        diff = diff.replace(0, np.nan)
        
        rsv = (close - low_min) / diff * 100
        k = rsv.ewm(com=2).mean()
        d = k.ewm(com=2).mean()
        
        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        loss = loss.replace(0, np.nan)
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        
        latest = df.iloc[-1]
        
        return {
            'date': str(df.index[-1].date()),
            'close': float(latest['Close']),
            'open': float(latest['Open']),
            'high': float(latest['High']),
            'low': float(latest['Low']),
            'volume': int(latest['Volume']),
            'ma5': float(ma5.iloc[-1]) if not pd.isna(ma5.iloc[-1]) else None,
            'ma20': float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else None,
            'ma60': float(ma60.iloc[-1]) if not pd.isna(ma60.iloc[-1]) else None,
            'k': float(k.iloc[-1]) if not pd.isna(k.iloc[-1]) else None,
            'd': float(d.iloc[-1]) if not pd.isna(d.iloc[-1]) else None,
            'rsi': float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None,
            'macd': float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else None,
            'signal': float(signal.iloc[-1]) if not pd.isna(signal.iloc[-1]) else None,
        }
    
    def batch_get_prices(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """批次獲取股價"""
        results = {}
        
        for i, code in enumerate(stock_codes):
            results[code] = self.get_price(code)
            
            # 每 5 個請求暫停一下
            if (i + 1) % 5 == 0:
                logger.info(f"已處理 {i+1}/{len(stock_codes)}，暫停...")
                time.sleep(2)
        
        return results


class TaiwanStockScreener:
    """台股篩選器 - FinMind API 整合版"""
    
    def __init__(self):
        self.base_url = "https://api.finmindtrade.com/api/v4/data"
        self.cache = StockDataCache()
    
    def get_all_stocks(self) -> Optional[List[Dict]]:
        """獲取所有台灣股票列表"""
        # 檢查快取
        cached = self.cache.get_cached_data('all_stocks', 'daily')
        if cached:
            return cached
        
        params = {
            "dataset": "TaiwanStockInfo",
            "data_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            data = response.json()
            
            if data.get('status') == 200:
                stocks = data.get('data', [])
                
                # 過濾
                filtered = [
                    s for s in stocks 
                    if s.get('industry_category') and 
                    not any(x in s.get('stock_id', '') for x in ['X', 'Y', 'Z'])
                ]
                
                # 儲存快取（1天）
                self.cache.save_cache('all_stocks', filtered, 'daily')
                return filtered
                
        except Exception as e:
            logger.error(f"獲取股票列表失敗: {e}")
        
        return None
    
    def get_daily_price(self, stock_id: str, days: int = 30) -> Optional[List[Dict]]:
        """獲取個股日線資料"""
        cache_key = f"price_{stock_id}_{days}d"
        cached = self.cache.get_cached_data(cache_key, f'{days}d')
        
        if cached:
            return cached
        
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            data = response.json()
            
            if data.get('status') == 200:
                price_data = data.get('data', [])
                self.cache.save_cache(cache_key, price_data, f'{days}d')
                return price_data
                
        except Exception as e:
            logger.error(f"獲取 {stock_id} 價格失敗: {e}")
        
        return None
    
    def screen_strong_stocks(self, min_volume: int = 1000, min_price: float = 10, limit: int = 20, target_date: str = None) -> List[Dict]:
        """篩選強勢股"""
        stocks = self.get_all_stocks()
        
        if not stocks:
            # 如果沒有股票資料，使用熱門股票列表
            stock_names = {
                '2330': '台積電', '2454': '聯發科', '2317': '鴻海', '2382': '廣達', '3711': '日月光',
                '3034': '聯詠', '3017': '奇鋐', '3231': '緯創', '2356': '英業達', '2353': '宏碁',
                '6282': '康舒', '4909': '新復興', '4908': '前鼎', '4977': '眾達-KY', '1590': '亞德客-KY',
                '2630': '亞航', '8112': '至上', '2374': '佳能'
            }
            stock_industries = {
                '2330': '半導體', '2454': 'IC設計', '2317': '電子', '2382': '電子', '3711': '半導體',
                '3034': 'IC設計', '3017': '散熱', '3231': '電子', '2356': '電子', '2353': '電子',
                '6282': '電源', '4909': '通訊', '4908': '光電', '4977': '光電', '1590': '氣動',
                '2630': '航太', '8112': '半導體', '2374': '光電'
            }
            stocks = [{'stock_id': code, 'stock_name': stock_names.get(code, ''), 'industry_category': stock_industries.get(code, '')} 
                      for code in ['2330','2454','2317','2382','3711','3034','3017','3231','2356','2353','6282','4909','4908','4977','1590','2630','8112','2374']]
        
        # 使用指定日期或今日
        if target_date:
            try:
                end_date = datetime.strptime(target_date, "%Y-%m-%d").strftime("%Y-%m-%d")
                start_date = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
            except:
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        else:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        strong_stocks = []
        
        # 測試所有熱門股票
        for i, stock in enumerate(stocks[:30]):
            stock_id = stock.get('stock_id')
            stock_name = stock.get('stock_name', '')
            
            price_data = self.get_daily_price(stock_id, 30)
            
            if price_data and len(price_data) > 0:
                latest = price_data[-1]
                
                # 基本篩選
                current_price = latest.get('close', 0)
                volume = latest.get('Trading_Volume', 0)
                
                if current_price > min_price and volume > min_volume * 1000:
                    # 計算動量
                    if len(price_data) >= 5:
                        returns = [(price_data[j]['close'] - price_data[j-1]['close']) / price_data[j-1]['close'] 
                                   for j in range(1, min(6, len(price_data))) if price_data[j-1].get('close',0) > 0]
                        momentum_5d = sum(returns) / len(returns) if returns else 0
                        
                        # 計算漲跌幅
                        if len(price_data) >= 2:
                            prev_price = price_data[-2].get('close', current_price)
                            change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price > 0 else 0
                        else:
                            change_pct = 0
                        
                        # 只要有正動量就加入
                        if momentum_5d > 0:
                            strong_stocks.append({
                                'code': stock_id,
                                'name': stock_name,
                                'industry': stock.get('industry_category', ''),
                                'price': current_price,
                                'volume': volume,
                                'momentum_5d': momentum_5d * 100,
                                'change_pct': change_pct
                            })
            
            # 頻率限制
            if (i + 1) % 10 == 0:
                time.sleep(1)
        
        # 按動量排序
        strong_stocks.sort(key=lambda x: x['momentum_5d'], reverse=True)
        
        # 按動量排序
        strong_stocks.sort(key=lambda x: x.get('momentum_5d', 0), reverse=True)
        return strong_stocks[:limit]


# ==================== 富果 API ====================
class FugleClient:
    """富果行情 API 客戶端"""
    
    def __init__(self, api_key: str = None):
        """初始化富果客戶端"""
        self.api_key = api_key or os.environ.get('FUGLE_API_KEY', '')
        self.base_url = 'https://api.fugle.tw/marketdata/v1.0'
        self.stock_api = None
        self._init_client()
    
    def _init_client(self):
        """初始化富果 API"""
        if not self.api_key:
            logger.warning('富果 API Key 未設定')
            return
        
        try:
            from fugle_marketdata import RestClient
            self.client = RestClient(api_key=self.api_key)
            self.stock_api = self.client.stock
            logger.info('富果 API 初始化成功')
        except ImportError:
            logger.warning('fugle-marketdata 未安裝，請執行 pip install fugle-marketdata')
        except Exception as e:
            logger.error(f'富果 API 初始化失敗: {e}')
    
    def get_quote(self, stock_code: str) -> Optional[Dict]:
        """取得個股報價"""
        # 優先嘗試 HTTP 直接請求（不依賴 SDK）
        try:
            import requests
            symbol_id = stock_code.replace('.TW', '').replace('.TWO', '')
            url = f'https://api.fugle.tw/marketdata/v1.0/stock/quote?symbolId={symbol_id}'
            headers = {'api-key': self.api_key}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('data'):
                    quote = data['data']
                    return {
                        'current_price': quote.get('close'),
                        'open': quote.get('open'),
                        'high': quote.get('high'),
                        'low': quote.get('low'),
                        'volume': quote.get('volume'),
                        'change': quote.get('change'),
                        'change_pct': quote.get('changePercent'),
                        'name': quote.get('name', '')
                    }
            else:
                logger.warning(f'富果 HTTP 请求失败: {resp.status_code} {resp.text}')
        except Exception as e:
            logger.error(f'富果 HTTP 请求异常: {e}')
        
        # SDK 備用
        if not self.stock_api:
            logger.warning('富果 API 未初始化，api_key: '+str(self.api_key[:10] if self.api_key else 'None')+'...')
            return None
        
        try:
            # 富果 API 需要去掉 .TW 後綴
            symbol_id = stock_code.replace('.TW', '').replace('.TWO', '')
            logger.info(f'富果 API 查詢: {symbol_id}')
            quote = self.stock_api.get_quote(symbolId=symbol_id)
            logger.info(f'富果 API 回應: {quote}')
            
            if quote:
                return {
                    'current_price': quote.get('close'),
                    'open': quote.get('open'),
                    'high': quote.get('high'),
                    'low': quote.get('low'),
                    'volume': quote.get('volume'),
                    'change': quote.get('change'),
                    'change_pct': quote.get('changePercent'),
                    'name': quote.get('name', '')
                }
            else:
                logger.warning(f'富果 API 回應空值 for {symbol_id}')
        except Exception as e:
            logger.error(f'富果取得 {stock_code} 報價失敗: {e}')
        
        return None
    
    def get_candles(self, stock_code: str, days: int = 90) -> Optional[Dict]:
        """取得 K 線資料"""
        if not self.stock_api:
            return None
        
        try:
            symbol_id = stock_code.replace('.TW', '').replace('.TWO', '')
            candles = self.stock_api.get_candles(symbolId=symbol_id, from_=f'now-{days}d')
            
            if candles and len(candles) > 0:
                # 計算技術指標
                import pandas as pd
                import numpy as np
                
                df = pd.DataFrame(candles)
                close = df['close']
                
                ma5 = close.rolling(5).mean().iloc[-1] if len(close) >= 5 else None
                ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else None
                ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else None
                
                # RSI
                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = (100 - (100 / (1 + rs))).iloc[-1] if len(rs) > 0 else None
                
                return {
                    'date': candles[-1].get('date'),
                    'close': candles[-1].get('close'),
                    'ma5': float(ma5) if ma5 and not pd.isna(ma5) else None,
                    'ma20': float(ma20) if ma20 and not pd.isna(ma20) else None,
                    'ma60': float(ma60) if ma60 and not pd.isna(ma60) else None,
                    'rsi': float(rsi) if rsi and not pd.isna(rsi) else None,
                    'volume': candles[-1].get('volume')
                }
        except Exception as e:
            logger.error(f'富果取得 {stock_code} K線失敗: {e}')
        
        return None
    
    def get_price_with_indicators(self, stock_code: str) -> Optional[Dict]:
        """取得報價與技術指標"""
        quote = self.get_quote(stock_code)
        candles = self.get_candles(stock_code, days=90)
        
        if not quote:
            return None
        
        result = {
            'current_price': quote.get('current_price') or quote.get('close'),
            'change_pct': quote.get('change_pct') or quote.get('changePercent'),
            'open': quote.get('open'),
            'high': quote.get('high'),
            'low': quote.get('low'),
            'volume': quote.get('volume'),
            'name': quote.get('name')
        }
        
        if candles:
            result.update({
                'ma5': candles.get('ma5'),
                'ma20': candles.get('ma20'),
                'ma60': candles.get('ma60'),
                'rsi': candles.get('rsi')
            })
        
        return result
