"""
Base optimizer class with common functionality
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from services.binance_service import BinanceService
from services.indicator_service import IndicatorService
from services.futures_backtest_service import FuturesBacktestService

class BaseOptimizer:
    """Base class for optimization functionality"""
    
    def __init__(self):
        self.binance_service = BinanceService()
        self.indicator_service = IndicatorService()
        self.backtest_service = FuturesBacktestService()
        
        # Data caching
        self.cache_dir = "optimizer_cache"
        self.ensure_cache_dir()
        
        # Results storage
        self.results_lock = threading.Lock()
        
    def ensure_cache_dir(self):
        """Ensure cache directory exists"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            print(f"Created cache directory: {self.cache_dir}")
    
    def get_cache_filename(self, symbol, interval, start_date, end_date):
        """Generate cache filename for data"""
        return f"{symbol}_{interval}_{start_date}_{end_date}.csv"
    
    def get_cache_filepath(self, symbol, interval, start_date, end_date):
        """Get full cache file path"""
        filename = self.get_cache_filename(symbol, interval, start_date, end_date)
        return os.path.join(self.cache_dir, filename)
    
    def load_cached_data(self, symbol, interval, start_date, end_date):
        """Load cached market data if available"""
        try:
            cache_path = self.get_cache_filepath(symbol, interval, start_date, end_date)
            
            if os.path.exists(cache_path):
                # Check if cache is not too old (max 1 day for historical data)
                cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))
                if cache_age.days <= 1:
                    print(f"Loading cached data for {symbol} from {cache_path}")
                    df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                    return df
                else:
                    print(f"Cache expired for {symbol}, will fetch fresh data")
                    os.remove(cache_path)  # Remove expired cache
            
            return None
        except Exception as e:
            print(f"Error loading cached data for {symbol}: {str(e)}")
            return None
    
    def save_cached_data(self, df, symbol, interval, start_date, end_date):
        """Save market data to cache"""
        try:
            cache_path = self.get_cache_filepath(symbol, interval, start_date, end_date)
            df.to_csv(cache_path)
            print(f"Saved cached data for {symbol} to {cache_path}")
        except Exception as e:
            print(f"Error saving cached data for {symbol}: {str(e)}")
    
    def get_market_data(self, symbol, interval, start_date, end_date):
        """Get market data with caching"""
        try:
            # Try to load from cache first
            cached_data = self.load_cached_data(symbol, interval, start_date, end_date)
            if cached_data is not None and not cached_data.empty:
                return cached_data
            
            # Fetch fresh data if not cached
            print(f"Fetching fresh data for {symbol}...")
            df = self.binance_service.get_klines(symbol, interval, start_date, end_date)
            
            if not df.empty:
                # Save to cache
                self.save_cached_data(df, symbol, interval, start_date, end_date)
                return df
            else:
                raise Exception(f"No data received for {symbol}")
                
        except Exception as e:
            print(f"Error getting market data for {symbol}: {str(e)}")
            raise e
    
    def get_cached_files(self):
        """Get list of cached data files"""
        try:
            cached_files = []
            if os.path.exists(self.cache_dir):
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.csv'):
                        filepath = os.path.join(self.cache_dir, filename)
                        file_size = os.path.getsize(filepath)
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        
                        cached_files.append({
                            'filename': filename,
                            'size': file_size,
                            'created': file_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'age_hours': (datetime.now() - file_time).total_seconds() / 3600
                        })
            
            return cached_files
        except Exception as e:
            print(f"Error getting cached files: {str(e)}")
            return []
    
    def clear_cache(self, older_than_hours=24):
        """Clear cached files older than specified hours"""
        try:
            cleared_count = 0
            if os.path.exists(self.cache_dir):
                current_time = datetime.now()
                
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith(('.csv', '.json')):
                        filepath = os.path.join(self.cache_dir, filename)
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        age_hours = (current_time - file_time).total_seconds() / 3600
                        
                        if age_hours > older_than_hours:
                            os.remove(filepath)
                            cleared_count += 1
                            print(f"Removed cached file: {filename}")
            
            # Also clear bulk cache directory
            bulk_cache_dir = os.path.join(self.cache_dir, "bulk_symbol_data")
            if os.path.exists(bulk_cache_dir):
                for filename in os.listdir(bulk_cache_dir):
                    if filename.endswith('.json'):
                        filepath = os.path.join(bulk_cache_dir, filename)
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        age_hours = (current_time - file_time).total_seconds() / 3600
                        
                        if age_hours > older_than_hours:
                            os.remove(filepath)
                            cleared_count += 1
                            print(f"Removed bulk cached file: {filename}")
            
            return cleared_count
        except Exception as e:
            print(f"Error clearing cache: {str(e)}")
            return 0