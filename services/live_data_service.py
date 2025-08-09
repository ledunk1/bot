import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from config.env_config import EnvConfig
from services.binance_service import BinanceService
from services.indicator_service import IndicatorService
from services.coin_settings_manager import CoinSettingsManager

class LiveDataService:
    def __init__(self):
        self.binance_service = BinanceService()
        self.indicator_service = IndicatorService()
        self.settings_manager = CoinSettingsManager()
        self.cache = {}
        self.cache_duration = EnvConfig.LIVE_DATA_CACHE_DURATION  # Use env config
        self.last_update_times = {}  # Track last update time per symbol
    
    def get_symbol_settings(self, symbol: str) -> dict:
        """Get strategy settings for a specific symbol"""
        try:
            coin_settings = self.settings_manager.load_coin_settings(symbol)
            
            if coin_settings.get('optimization_score', 0) > 0:
                # Use optimized settings
                print(f"📊 Using optimized settings for {symbol} (Score: {coin_settings['optimization_score']:.2f})")
                return coin_settings['strategy_params']
            else:
                # Use default settings
                default_settings = {
                    'macd_fast': 14,
                    'macd_slow': 32,
                    'macd_signal': 10,
                    'sma_length': 150
                }
                return default_settings
        except Exception as e:
            print(f"⚠️ Error getting settings for {symbol}, using default: {str(e)}")
            return {
                'macd_fast': 14,
                'macd_slow': 32,
                'macd_signal': 10,
                'sma_length': 150
            }
    
    def get_live_data(self, symbol, interval='1h', limit=100):
        """Get live data for a single symbol with caching"""
        try:
            cache_key = f"{symbol}_{interval}_{limit}"
            current_time = time.time()
            
            # Check cache with very short duration for live updates
            if (cache_key in self.cache and 
                current_time - self.cache[cache_key]['timestamp'] < 10):  # 10 seconds cache
                print(f"Returning cached data for {symbol}")
                return self.cache[cache_key]['data']
            
            print(f"Fetching fresh data for {symbol} - {interval}")
            
            # Get recent data (last 100 + buffer for indicators)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self._get_days_for_candles(interval, limit + 250))
            
            # Get klines data
            df = self.binance_service.get_klines(
                symbol, interval, 
                start_date.strftime('%Y-%m-%d'), 
                end_date.strftime('%Y-%m-%d')
            )
            
            if df.empty:
                print(f"No data received for {symbol}")
                return None
            
            print(f"Received {len(df)} candles for {symbol}")
            
            # Calculate indicators
            # Get symbol-specific settings
            strategy_params = self.get_symbol_settings(symbol)
            
            df_with_indicators = self.indicator_service.calculate_indicators(df, strategy_params)
            signals = self.indicator_service.generate_signals(df_with_indicators, strategy_params)
            
            # Get last N candles
            recent_data = df_with_indicators.tail(limit).copy()
            recent_signals = signals.tail(limit).copy()
            
            print(f"Processed {len(recent_data)} candles with indicators for {symbol}")
            
            # Prepare chart data
            chart_data = []
            for timestamp, row in recent_data.iterrows():
                signal_info = recent_signals.loc[timestamp] if timestamp in recent_signals.index else None
                
                candle = {
                    'timestamp': timestamp.isoformat(),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                    'fast_ma': float(row['fast_ma']) if 'fast_ma' in row and not pd.isna(row['fast_ma']) else None,
                    'slow_ma': float(row['slow_ma']) if 'slow_ma' in row and not pd.isna(row['slow_ma']) else None,
                    'very_slow_ma': float(row['very_slow_ma']) if 'very_slow_ma' in row and not pd.isna(row['very_slow_ma']) else None,
                    'signal': int(signal_info['signal']) if signal_info is not None else 0,
                    'signal_strength': float(signal_info['signal_strength']) if signal_info is not None else 0
                }
                chart_data.append(candle)
            
            # Get latest signal info
            latest_signal = recent_signals.iloc[-1] if not recent_signals.empty else None
            latest_candle = recent_data.iloc[-1] if not recent_data.empty else None
            
            # Check if this is a new candle (price changed significantly)
            is_new_data = False
            if symbol in self.last_update_times:
                last_price = self.last_update_times[symbol].get('price', 0)
                last_time = self.last_update_times[symbol].get('time', 0)
                current_price = float(latest_candle['close']) if latest_candle is not None else 0
                
                # Consider new data if price changed significantly OR enough time passed
                price_changed = abs(current_price - last_price) > (current_price * 0.001)  # 0.1% change
                time_passed = current_time - last_time > 60  # 1 minute passed
                is_new_data = price_changed or time_passed
                
                print(f"Data freshness check for {symbol}: price_changed={price_changed}, time_passed={time_passed}, is_new={is_new_data}")
            
            # Update last update time and price
            self.last_update_times[symbol] = {
                'time': current_time,
                'price': float(latest_candle['close']) if latest_candle is not None else 0
            }
            
            result = {
                'symbol': symbol,
                'chart_data': chart_data,
                'latest_signal': {
                    'signal': int(latest_signal['signal']) if latest_signal is not None else 0,
                    'signal_strength': float(latest_signal['signal_strength']) if latest_signal is not None else 0,
                    'price': float(latest_candle['close']) if latest_candle is not None else 0,
                    'timestamp': latest_candle.name.isoformat() if latest_candle is not None else None
                },
                'settings_used': strategy_params,
                'is_optimized': self.settings_manager.load_coin_settings(symbol).get('optimization_score', 0) > 0,
                'last_update': current_time,
                'is_new_data': is_new_data,
                'market_status': 'open'  # You can enhance this with actual market hours
            }
            
            # Cache result
            self.cache[cache_key] = {
                'data': result,
                'timestamp': current_time
            }
            
            print(f"Successfully prepared live data for {symbol} with {len(chart_data)} candles")
            return result
            
        except Exception as e:
            print(f"Error getting live data for {symbol}: {str(e)}")
            return None
    
    def get_real_time_price(self, symbol):
        """Get real-time price for a symbol (minimal data for quick updates)"""
        try:
            # Get just the latest candle for price updates
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=2)  # Just last 2 hours
            
            df = self.binance_service.get_klines(
                symbol, '1m',  # Use 1-minute candles for more frequent updates
                start_date.strftime('%Y-%m-%d %H:%M:%S'), 
                end_date.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            if df.empty:
                return None
            
            latest = df.iloc[-1]
            return {
                'symbol': symbol,
                'price': float(latest['close']),
                'change': float(latest['close'] - latest['open']),
                'change_percent': ((float(latest['close']) - float(latest['open'])) / float(latest['open'])) * 100,
                'volume': float(latest['volume']),
                'timestamp': latest.name.isoformat(),
                'high_24h': float(df['high'].max()),
                'low_24h': float(df['low'].min())
            }
            
        except Exception as e:
            print(f"Error getting real-time price for {symbol}: {str(e)}")
            return None
    
    def scan_all_symbols(self, interval='1h', min_signal_strength=0.3):
        """Scan all symbols for buy/sell signals"""
        try:
            # Get all symbols
            symbols = self.binance_service.get_futures_symbols()
            signals_found = []
            
            print(f"Scanning {len(symbols)} symbols for signals...")
            
            for i, symbol_info in enumerate(symbols):
                symbol = symbol_info['symbol']
                
                # Skip stablecoins and low volume pairs
                if any(stable in symbol for stable in ['BUSD', 'TUSD', 'USDC', 'DAI']):
                    continue
                
                try:
                    data = self.get_live_data(symbol, interval, 100)
                    
                    if data and data['latest_signal']:
                        signal = data['latest_signal']['signal']
                        strength = data['latest_signal']['signal_strength']
                        
                        if signal != 0 and strength >= min_signal_strength:
                            signals_found.append({
                                'symbol': symbol,
                                'signal': 'BUY' if signal == 1 else 'SELL',
                                'signal_value': signal,
                                'strength': strength,
                                'price': data['latest_signal']['price'],
                                'timestamp': data['latest_signal']['timestamp'],
                                'chart_data': data['chart_data']
                            })
                            
                            print(f"Signal found: {symbol} - {signal} (strength: {strength:.2f})")
                    
                    # Progress indicator
                    if (i + 1) % 50 == 0:
                        print(f"Scanned {i + 1}/{len(symbols)} symbols...")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Error scanning {symbol}: {str(e)}")
                    continue
            
            print(f"Scan completed. Found {len(signals_found)} signals.")
            return signals_found
            
        except Exception as e:
            print(f"Error in scan_all_symbols: {str(e)}")
            return []
    
    def _get_days_for_candles(self, interval, candles):
        """Calculate days needed for number of candles"""
        interval_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720,
            '1d': 1440
        }
        
        minutes_needed = candles * interval_minutes.get(interval, 60)
        days_needed = max(1, int(minutes_needed / 1440) + 1)
        
        return min(days_needed, 365)  # Max 1 year