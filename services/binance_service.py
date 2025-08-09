from binance import Client
import pandas as pd
from datetime import datetime
import time
from config.settings import Config

class BinanceService:
    def __init__(self):
        # Initialize client without API keys for public data
        try:
            # Use production for public data
            self.client = Client(testnet=False)
            print("✅ Binance public client initialized")
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize Binance client: {str(e)}")
            self.client = None
        self.base_url = "https://fapi.binance.com"  # Production API
        self.max_klines_per_request = 1000  # Binance limit per request
        
    def get_futures_symbols(self):
        """Get all available futures trading symbols using python-binance"""
        try:
            if not self.client:
                raise Exception("Binance client not initialized")
                
            # Get exchange info for futures
            exchange_info = self.client.futures_exchange_info()
            symbols = []
            
            for symbol_info in exchange_info['symbols']:
                if (symbol_info['status'] == 'TRADING' and 
                    symbol_info['contractType'] == 'PERPETUAL' and
                    symbol_info['quoteAsset'] == 'USDT'):
                    symbols.append({
                        'symbol': symbol_info['symbol'],
                        'baseAsset': symbol_info['baseAsset'],
                        'quoteAsset': symbol_info['quoteAsset']
                    })
            
            # Sort symbols alphabetically
            symbols.sort(key=lambda x: x['symbol'])
            
            print(f"Found {len(symbols)} trading symbols")
            
            # Return all symbols (no limit)
            return symbols
        except Exception as e:
            print(f"Error in get_futures_symbols: {str(e)}")
            raise Exception(f"Error fetching symbols: {str(e)}")
    
    def get_klines(self, symbol, interval, start_date, end_date):
        """Get candlestick data using python-binance with pagination for large datasets"""
        try:
            print(f"Fetching klines for {symbol} from {start_date} to {end_date}")
            
            # Convert dates to timestamps for pagination
            start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
            end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)
            
            all_klines = []
            current_start = start_ts
            
            print(f"Fetching data in batches (max {self.max_klines_per_request} per request)...")
            
            while current_start < end_ts:
                try:
                    # Get batch of klines
                    batch_klines = self.client.futures_historical_klines(
                        symbol=symbol,
                        interval=interval,
                        start_str=current_start,
                        end_str=end_ts,
                        limit=self.max_klines_per_request
                    )
                    
                    if not batch_klines:
                        print("No more data available")
                        break
                    
                    print(f"Fetched batch: {len(batch_klines)} klines")
                    all_klines.extend(batch_klines)
                    
                    # Update start time for next batch (use last kline's close time + 1ms)
                    last_kline_close_time = int(batch_klines[-1][6])  # close_time
                    current_start = last_kline_close_time + 1
                    
                    # Add small delay to avoid rate limiting
                    time.sleep(0.1)
                    
                    # Break if we got less than max limit (means we reached the end)
                    if len(batch_klines) < self.max_klines_per_request:
                        break
                        
                except Exception as batch_error:
                    print(f"Error in batch request: {str(batch_error)}")
                    # Try to continue with next batch
                    current_start += 60000 * self._get_interval_minutes(interval)  # Skip forward
                    continue
            
            # Remove duplicates based on timestamp
            seen_timestamps = set()
            unique_klines = []
            for kline in all_klines:
                timestamp = kline[0]
                if timestamp not in seen_timestamps:
                    seen_timestamps.add(timestamp)
                    unique_klines.append(kline)
            
            klines = unique_klines
            
            if not klines:
                raise Exception("No data available for the specified date range")
            
            print(f"Total retrieved: {len(klines)} unique klines")
            
            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # Convert data types
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Remove duplicates and sort
            df = df[~df.index.duplicated(keep='first')]
            df = df.sort_index()
            
            # Filter by exact date range
            start_filter = pd.Timestamp(start_date)
            end_filter = pd.Timestamp(end_date)
            
            print(f"Filtering data: start={start_filter}, end={end_filter}")
            print(f"Data range before filter: {df.index.min()} to {df.index.max()}")
            
            df = df[(df.index >= start_filter) & (df.index <= end_filter)]
            
            print(f"Data range after filter: {df.index.min()} to {df.index.max()}")
            print(f"Processed DataFrame with {len(df)} rows (filtered from {len(unique_klines)} total)")
            
            return df
        except Exception as e:
            print(f"Error in get_klines: {str(e)}")
            raise Exception(f"Error fetching klines: {str(e)}")
    
    def _get_interval_minutes(self, interval):
        """Convert interval string to minutes"""
        interval_map = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720,
            '1d': 1440, '3d': 4320, '1w': 10080, '1M': 43200
        }
        return interval_map.get(interval, 60)