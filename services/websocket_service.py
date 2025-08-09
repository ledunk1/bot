import websocket
import json
import threading
import time
import queue
from datetime import datetime
import pandas as pd
from services.indicator_service import IndicatorService
from services.telegram_service import TelegramService
from services.coin_settings_manager import CoinSettingsManager

class WebSocketService:
    def __init__(self, telegram_bot_token=None, telegram_chat_id=None, trading_service=None):
        # Use environment config if tokens not provided
        from config.env_config import EnvConfig
        env_config = EnvConfig()
        
        # Use provided tokens or fall back to env config
        bot_token = telegram_bot_token or env_config.TELEGRAM_BOT_TOKEN
        chat_id = telegram_chat_id or env_config.TELEGRAM_CHAT_ID
        
        print(f"🔧 WebSocket service initializing with bot_token: {bot_token[:10] if bot_token else 'None'}..., chat_id: {chat_id}")
        
        self.ws = None
        self.is_running = False
        self.should_reconnect = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 50
        self.reconnect_delay = 5  # Start with 5 seconds
        self.max_reconnect_delay = 60  # Max 1 minute for faster recovery
        self.timeframe = '1h'  # Default timeframe
        self.subscribed_symbols = set()
        self.candle_data = {}  # Store candle data for each symbol
        self.indicator_service = IndicatorService()
        self.telegram_service = TelegramService(bot_token, chat_id, trading_service)
        self.settings_manager = CoinSettingsManager()
        self.trading_service = trading_service
        self.last_signals = {}  # Track last signals to avoid duplicates
        self.ws_thread = None
        self.connection_lock = threading.Lock()
        
        # Signal buffering system
        self.signal_buffer = queue.Queue()
        self.signal_processor_thread = None
        self.signal_processing = False
        
        # Connection health monitoring
        self.last_message_time = time.time()
        self.health_check_thread = None
        self.health_check_running = False
        
        # Enhanced reconnection strategy
        self.connection_stable = False
        self.stable_connection_time = 0
        self.min_stable_time = 30  # Minimum 30 seconds stable before considering healthy
        
        # WebSocket URLs
        # Always use production WebSocket URL
        self.ws_url = "wss://fstream.binance.com/ws/"
        
        # Strategy parameters
        self.strategy_params = {
            'macd_fast': 14,
            'macd_slow': 32,
            'macd_signal': 10,
            'sma_length': 150
        }
        
        # Minimum data points needed for indicators
        self.min_data_points = 250
        
        # Start signal processor
        self._start_signal_processor()
        
        # Start health monitor
        self._start_health_monitor()
    
    def _start_signal_processor(self):
        """Start background signal processor"""
        if not self.signal_processing:
            self.signal_processing = True
            self.signal_processor_thread = threading.Thread(target=self._process_signal_buffer, daemon=True)
            self.signal_processor_thread.start()
            print("📡 Signal processor started")
    
    def _start_health_monitor(self):
        """Start connection health monitor"""
        if not self.health_check_running:
            self.health_check_running = True
            self.health_check_thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
            self.health_check_thread.start()
            print("🏥 Health monitor started")
    
    def _process_signal_buffer(self):
        """Process buffered signals to ensure delivery"""
        while self.signal_processing:
            try:
                # Get signal from buffer with timeout
                signal_data = self.signal_buffer.get(timeout=5)
                
                if signal_data is None:
                    continue
                
                # Try to send signal with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        success = self.telegram_service.send_enhanced_signal_notification(signal_data)
                        
                        if success:
                            print(f"✅ Signal sent successfully: {signal_data['symbol']} - {signal_data['signal']}")
                            break
                        else:
                            print(f"⚠️ Signal send failed (attempt {attempt + 1}/{max_retries}): {signal_data['symbol']}")
                            if attempt < max_retries - 1:
                                time.sleep(2 ** attempt)  # Exponential backoff
                    except Exception as e:
                        print(f"❌ Error sending signal (attempt {attempt + 1}/{max_retries}): {str(e)}")
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)
                
                self.signal_buffer.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in signal processor: {str(e)}")
                time.sleep(5)
    
    def _health_monitor_loop(self):
        """Monitor connection health and force reconnect if needed"""
        while self.health_check_running:
            try:
                current_time = time.time()
                
                # Check if we haven't received messages for too long
                time_since_last_message = current_time - self.last_message_time
                
                if self.is_running and time_since_last_message > 120:  # 2 minutes without messages
                    print(f"⚠️ No messages received for {time_since_last_message:.0f} seconds, forcing reconnect...")
                    self._force_reconnect()
                
                # Update connection stability
                if self.is_running and time_since_last_message < 60:
                    if not self.connection_stable:
                        self.stable_connection_time = current_time
                        self.connection_stable = True
                        print("✅ Connection stabilized")
                elif time_since_last_message > 60:
                    self.connection_stable = False
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                print(f"Error in health monitor: {str(e)}")
                time.sleep(30)
    
    def _force_reconnect(self):
        """Force WebSocket reconnection"""
        try:
            print("🔄 Forcing WebSocket reconnection...")
            
            # Close current connection
            if self.ws:
                self.ws.close()
            
            self.is_running = False
            time.sleep(5)  # Wait before reconnecting
            
            # Reconnect if should_reconnect is still True
            if self.should_reconnect:
                self._connect_websocket()
                
        except Exception as e:
            print(f"Error in force reconnect: {str(e)}")
        
    def get_symbol_settings(self, symbol: str) -> dict:
        """Get strategy settings for a specific symbol"""
        try:
            coin_settings = self.settings_manager.load_coin_settings(symbol)
            
            if coin_settings.get('optimization_score', 0) > 0:
                # Use optimized settings
                return coin_settings['strategy_params']
            else:
                # Use default settings
                return self.strategy_params
        except Exception as e:
            print(f"⚠️ Error getting settings for {symbol}, using default: {str(e)}")
            return self.strategy_params
    
    def start_websocket(self, symbols=None, timeframe='1h'):
        """Start WebSocket connection for multiple symbols"""
        if self.is_running:
            print("WebSocket is already running")
            return
            
        # Set timeframe
        self.timeframe = timeframe
        
        if symbols is None:
            # Default popular symbols
            symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT', 
                      'LINKUSDT', 'AVAXUSDT', 'MATICUSDT', 'ATOMUSDT', 'NEARUSDT']
        
        # Remove duplicates and limit symbols
        symbols = list(set(symbols))
        print(f"Requested {len(symbols)} symbols for WebSocket monitoring")
        
        self.subscribed_symbols = set(symbols)
        self.should_reconnect = True
        self.reconnect_attempts = 0
        self.last_message_time = time.time()  # Reset message timer
        
        # Initialize candle data storage
        for symbol in symbols:
            self.candle_data[symbol] = []
            self.last_signals[symbol] = {'signal': 0, 'timestamp': None}
        
        # Start WebSocket connection
        self._connect_websocket()
        
        # Initialize historical data for all symbols
        self._initialize_historical_data()
    
    def _connect_websocket(self):
        """Connect to WebSocket with reconnection logic"""
        try:
            with self.connection_lock:
                if self.ws and self.is_running:
                    print("WebSocket connection already in progress")
                    return
                
            # Create stream names for all symbols (max 1024 streams per connection)
            symbols_list = list(self.subscribed_symbols)
            
            # Binance WebSocket limit is 1024 streams, but we'll use a more conservative limit
            max_streams_per_connection = 200
            
            if len(symbols_list) > max_streams_per_connection:
                print(f"⚠️ Too many symbols ({len(symbols_list)}), limiting to {max_streams_per_connection}")
                symbols_list = symbols_list[:max_streams_per_connection]
                self.subscribed_symbols = set(symbols_list)
            
            # Create combined stream URL for multiple symbols
            if len(symbols_list) == 1:
                # Single stream
                stream_url = f"wss://fstream.binance.com/ws/{symbols_list[0].lower()}@kline_{self.timeframe}"
            else:
                # Multiple streams
                streams = [f"{symbol.lower()}@kline_{self.timeframe}" for symbol in symbols_list]
                stream_url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"
            
            print(f"Connecting WebSocket for {len(symbols_list)} symbols with {self.timeframe} timeframe")
            print(f"Symbols: {symbols_list[:10]}{'...' if len(symbols_list) > 10 else ''}")
            print(f"WebSocket URL: {stream_url[:100]}...")
            
            self.ws = websocket.WebSocketApp(
                stream_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Start WebSocket in separate thread only if not already running
            if not self.ws_thread or not self.ws_thread.is_alive():
                self.ws_thread = threading.Thread(target=self._run_websocket_with_reconnect, daemon=True)
                self.ws_thread.start()
            
        except Exception as e:
            print(f"Error connecting WebSocket: {str(e)}")
    
    def _run_websocket_with_reconnect(self):
        """Run WebSocket with automatic reconnection"""
        while self.should_reconnect:
            try:
                if self.reconnect_attempts > 0:
                    print(f"WebSocket reconnection attempt {self.reconnect_attempts}")
                
                self.is_running = True
                self.ws.run_forever(
                    ping_interval=30,  # Send ping every 30 seconds
                    ping_timeout=15,   # Wait 15 seconds for pong
                    reconnect=3        # Reconnect after 3 seconds if connection fails
                )
            except Exception as e:
                print(f"WebSocket run error: {str(e)}")
                self.is_running = False
            
            if self.should_reconnect:
                self.reconnect_attempts += 1
                
                # Progressive backoff with faster initial reconnects
                if self.reconnect_attempts <= 3:
                    wait_time = 2  # Quick reconnect for first 3 attempts
                elif self.reconnect_attempts <= 10:
                    wait_time = 5  # Medium delay for next 7 attempts
                else:
                    wait_time = min(15, self.reconnect_attempts)  # Longer delay after 10 attempts
                
                print(f"Reconnecting in {wait_time:.1f} seconds... (attempt {self.reconnect_attempts})")
                time.sleep(wait_time)
                
                # Reset WebSocket object for clean reconnection
                with self.connection_lock:
                    self.ws = None
                
                # Recreate WebSocket connection
                try:
                    self._connect_websocket()
                except Exception as e:
                    print(f"Error during reconnection: {str(e)}")
                    continue
        
        
    def stop_websocket(self):
        """Stop WebSocket connection"""
        print("Stopping WebSocket...")
        self.should_reconnect = False
        self.is_running = False
        self.signal_processing = False
        self.health_check_running = False
        
        if self.ws:
            self.ws.close()
            
    def _on_open(self, ws):
        print(f"✅ WebSocket connected for {len(self.subscribed_symbols)} symbols")
        self.reconnect_attempts = 0  # Reset reconnect attempts on successful connection
        self.reconnect_delay = 5  # Reset reconnect delay
        self.last_message_time = time.time()  # Reset message timer
        self.connection_stable = False  # Will be set to True by health monitor
        
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # Update last message time for health monitoring
            self.last_message_time = time.time()
            
            data = json.loads(message)
            
            # Handle single stream data
            if 'stream' in data:
                stream_data = data['data']
                self._process_kline_data(stream_data)
            # Handle multi-stream data
            elif 'k' in data:
                self._process_kline_data(data)
            else:
                # Handle other message types (ping/pong, etc.)
                pass
                
        except Exception as e:
            print(f"Error processing WebSocket message: {str(e)}")
            
    def _on_error(self, ws, error):
        print(f"❌ WebSocket error: {error}")
        self.is_running = False
        self.connection_stable = False
        
    def _on_close(self, ws, close_status_code, close_msg):
        print(f"🔌 WebSocket connection closed (code: {close_status_code}, msg: {close_msg})")
        self.is_running = False
        self.connection_stable = False
        if self.should_reconnect:
            print("🔄 Attempting to reconnect...")
        
    def _process_kline_data(self, kline_data):
        """Process incoming kline data and check for signals"""
        try:
            kline = kline_data['k']
            symbol = kline['s']
            
            # Only process if kline is closed
            if not kline['x']:  # x = is_closed
                return
                
            # Create candle data
            candle = {
                'timestamp': pd.to_datetime(kline['t'], unit='ms'),
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v'])
            }
            
            # Update candle data for symbol
            if symbol not in self.candle_data:
                self.candle_data[symbol] = []
                
            self.candle_data[symbol].append(candle)
            
            # Keep only last 300 candles (enough for indicators)
            if len(self.candle_data[symbol]) > 300:
                self.candle_data[symbol] = self.candle_data[symbol][-300:]
            
            # Check for signals if we have enough data
            if len(self.candle_data[symbol]) >= self.min_data_points:
                self._check_signals(symbol)
            else:
                print(f"📊 {symbol}: Collecting data... {len(self.candle_data[symbol])}/{self.min_data_points}")
                
            print(f"Updated {symbol}: Price ${candle['close']:.4f}, Data points: {len(self.candle_data[symbol])}")
            
        except Exception as e:
            print(f"Error processing kline data: {str(e)}")
            
    def _initialize_historical_data(self):
        """Initialize historical data for all symbols"""
        from services.binance_service import BinanceService
        binance_service = BinanceService()
        
        print("Initializing historical data...")
        
        for symbol in self.subscribed_symbols:
            try:
                # Get last 250 candles for indicators
                from datetime import timedelta
                end_date = datetime.now()
                
                # Calculate days needed based on timeframe
                days_needed = self._get_days_for_timeframe(self.timeframe, 250)
                start_date = end_date - timedelta(days=days_needed)
                
                df = binance_service.get_klines(
                    symbol, self.timeframe,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )
                
                if not df.empty:
                    # Convert to list format
                    candles = []
                    for timestamp, row in df.iterrows():
                        candles.append({
                            'timestamp': timestamp,
                            'open': float(row['open']),
                            'high': float(row['high']),
                            'low': float(row['low']),
                            'close': float(row['close']),
                            'volume': float(row['volume'])
                        })
                    
                    self.candle_data[symbol] = candles[-250:]  # Keep last 250
                    print(f"Initialized {symbol} with {len(self.candle_data[symbol])} historical candles")
                    
            except Exception as e:
                print(f"Error initializing historical data for {symbol}: {str(e)}")
                
        print("Historical data initialization completed")
        
    def _get_days_for_timeframe(self, timeframe, candles_needed):
        """Calculate days needed for timeframe and number of candles"""
        timeframe_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720,
            '1d': 1440
        }
        
        minutes_per_candle = timeframe_minutes.get(timeframe, 60)
        total_minutes = candles_needed * minutes_per_candle
        days = max(1, int(total_minutes / 1440) + 1)
        
        return min(days, 30)  # Max 30 days
        
    def _check_signals(self, symbol):
        """Check for trading signals on symbol"""
        try:
            candles = self.candle_data[symbol]
            if len(candles) < self.min_data_points:
                return
                
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            df.set_index('timestamp', inplace=True)
            
            # Calculate indicators
            # Get symbol-specific settings
            symbol_settings = self.get_symbol_settings(symbol)
            
            df_with_indicators = self.indicator_service.calculate_indicators(df, symbol_settings)
            signals = self.indicator_service.generate_signals(df_with_indicators, symbol_settings)
            
            if signals.empty:
                return
                
            # Get latest signal
            latest_signal = signals.iloc[-1]
            latest_timestamp = signals.index[-1]
            
            # Check if this is a new signal
            last_signal = self.last_signals.get(symbol, {'signal': 0, 'timestamp': None})
            
            # Enhanced signal detection with better duplicate prevention
            signal_changed = latest_signal['signal'] != last_signal['signal']
            time_changed = latest_timestamp != last_signal['timestamp']
            signal_strength_ok = latest_signal['signal_strength'] >= 0.3
            
            if (latest_signal['signal'] != 0 and 
                signal_changed and time_changed and signal_strength_ok):
                
                # Enhanced auto trading check - handle opposite signals
                if (self.trading_service and 
                    self.trading_service.is_connected and 
                    self.trading_service.trading_settings['auto_trading']['enabled']):
                    
                    # Check if this is an opposite signal for existing position
                    if symbol in self.trading_service.active_positions:
                        existing_position = self.trading_service.active_positions[symbol]
                        if existing_position['is_active']:
                            existing_side = existing_position['side']
                            new_signal_side = 'BUY' if latest_signal['signal'] == 1 else 'SELL'
                            
                            # If opposite signal, prioritize auto trading
                            if ((existing_side == 'BUY' and new_signal_side == 'SELL') or 
                                (existing_side == 'SELL' and new_signal_side == 'BUY')):
                                print(f"🔄 Opposite signal detected for auto trading: {symbol} {existing_side} → {new_signal_side}")
                                
                                # Prepare signal data for auto trading
                                signal_data = self._prepare_signal_data(symbol, latest_signal, latest_timestamp, df_with_indicators)
                                signal_data['settings_used'] = symbol_settings
                                signal_data['is_optimized'] = self.settings_manager.load_coin_settings(symbol).get('optimization_score', 0) > 0
                                signal_data['is_opposite_signal'] = True
                                signal_data['existing_position'] = existing_side
                                
                                # Execute auto trade immediately for opposite signals
                                try:
                                    success, result = self.trading_service.execute_auto_trade(
                                        symbol, new_signal_side, latest_signal['price'], signal_data
                                    )
                                    
                                    if success:
                                        print(f"🤖 Auto trade executed for opposite signal: {symbol} {new_signal_side}")
                                        
                                        # Send enhanced notification about auto trade
                                        enhanced_signal_data = signal_data.copy()
                                        enhanced_signal_data['auto_trade_executed'] = True
                                        enhanced_signal_data['auto_trade_result'] = result
                                        enhanced_signal_data['trade_action'] = f"Closed {existing_side} → Opened {new_signal_side}"
                                        
                                        # Add to buffer for notification
                                        self.signal_buffer.put(enhanced_signal_data, timeout=1)
                                        
                                        # Update last signal to prevent duplicate processing
                                        self.last_signals[symbol] = {
                                            'signal': latest_signal['signal'],
                                            'timestamp': latest_timestamp
                                        }
                                        
                                        return  # Exit early - signal processed via auto trade
                                    else:
                                        print(f"❌ Auto trade failed for opposite signal: {symbol} - {result}")
                                        # Continue with normal signal processing
                                        
                                except Exception as e:
                                    print(f"❌ Error in auto trade for opposite signal: {str(e)}")
                                    # Continue with normal signal processing
                            else:
                                # Same direction signal with existing position - skip signal
                                print(f"⏭️ Skipping same direction signal for {symbol}: {existing_side} (already have position)")
                                return
                
                # New signal detected!
                signal_data = self._prepare_signal_data(symbol, latest_signal, latest_timestamp, df_with_indicators)
                
                # Add settings info to signal data
                signal_data['settings_used'] = symbol_settings
                signal_data['is_optimized'] = self.settings_manager.load_coin_settings(symbol).get('optimization_score', 0) > 0
                
                # Add signal to buffer for reliable delivery
                try:
                    self.signal_buffer.put(signal_data, timeout=1)
                    print(f"🚨 NEW SIGNAL BUFFERED: {symbol} - {'BUY' if latest_signal['signal'] == 1 else 'SELL'} at ${latest_signal['price']:.4f}")
                    
                    # Update last signal immediately to prevent duplicates
                    self.last_signals[symbol] = {
                        'signal': latest_signal['signal'],
                        'timestamp': latest_timestamp
                    }
                    
                except queue.Full:
                    print(f"⚠️ Signal buffer full, dropping signal for {symbol}")
                
            elif latest_signal['signal'] != 0 and not signal_strength_ok:
                print(f"⚠️ Weak signal filtered for {symbol}: strength {latest_signal['signal_strength']:.2f} < 0.3")
                    
        except Exception as e:
            print(f"Error checking signals for {symbol}: {str(e)}")
            
    def _prepare_signal_data(self, symbol, signal, timestamp, df_with_indicators):
        """Prepare comprehensive signal data for Telegram"""
        try:
            current_price = signal['price']
            signal_type = 'BUY' if signal['signal'] == 1 else 'SELL'
            direction = signal['signal']
            
            # Calculate TP and SL levels
            tp_levels, sl_level = self._calculate_tp_sl_levels(current_price, direction)
            
            # Prepare chart data (last 100 candles)
            chart_data = []
            recent_data = df_with_indicators.tail(100)
            
            for ts, row in recent_data.iterrows():
                chart_data.append({
                    'timestamp': ts.isoformat(),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                    'fast_ma': float(row['fast_ma']) if 'fast_ma' in row and not pd.isna(row['fast_ma']) else None,
                    'slow_ma': float(row['slow_ma']) if 'slow_ma' in row and not pd.isna(row['slow_ma']) else None,
                    'very_slow_ma': float(row['very_slow_ma']) if 'very_slow_ma' in row and not pd.isna(row['very_slow_ma']) else None,
                    'signal': direction if ts == timestamp else 0
                })
            
            return {
                'symbol': symbol,
                'signal': signal_type,
                'signal_value': direction,
                'price': current_price,
                'strength': signal['signal_strength'],
                'timestamp': timestamp.isoformat(),
                'entry_price': current_price,
                'tp_levels': tp_levels,
                'sl_level': sl_level,
                'chart_data': chart_data,
                'strategy': 'MACD + SMA 200',
                'timeframe': self.timeframe.upper()
            }
            
        except Exception as e:
            print(f"Error preparing signal data: {str(e)}")
            return None
            
    def _calculate_tp_sl_levels(self, entry_price, direction):
        """Calculate TP and SL levels"""
        tp_base_percent = 0.75
        sl_percent = 1.50
        max_tps = 5
        
        tp_levels = []
        
        # Calculate TP levels
        for i in range(1, max_tps + 1):
            tp_percent = tp_base_percent * i
            
            if direction == 1:  # Long
                tp_price = entry_price * (1 + tp_percent / 100)
            else:  # Short
                tp_price = entry_price * (1 - tp_percent / 100)
                
            tp_levels.append({
                'level': i,
                'price': tp_price,
                'percent': tp_percent
            })
        
        # Calculate SL level
        if direction == 1:  # Long
            sl_price = entry_price * (1 - sl_percent / 100)
        else:  # Short
            sl_price = entry_price * (1 + sl_percent / 100)
            
        return tp_levels, sl_price
        
    def get_live_data(self, symbol):
        """Get current live data for a symbol"""
        if symbol not in self.candle_data or not self.candle_data[symbol]:
            return None
            
        candles = self.candle_data[symbol]
        latest_candle = candles[-1]
        
        return {
            'symbol': symbol,
            'price': latest_candle['close'],
            'timestamp': latest_candle['timestamp'].isoformat(),
            'candles': candles[-100:],  # Last 100 candles
            'is_live': self.is_running,
            'connection_stable': self.connection_stable,
            'data_points': len(candles)
        }
        
    def get_all_symbols_data(self):
        """Get live data for all subscribed symbols"""
        result = {}
        for symbol in self.subscribed_symbols:
            result[symbol] = self.get_live_data(symbol)
        return result
    
    def get_connection_health(self):
        """Get connection health status"""
        current_time = time.time()
        time_since_last_message = current_time - self.last_message_time
        
        return {
            'is_connected': self.is_running,
            'is_stable': self.connection_stable,
            'time_since_last_message': time_since_last_message,
            'reconnect_attempts': self.reconnect_attempts,
            'signal_buffer_size': self.signal_buffer.qsize(),
            'symbols_with_data': len([s for s in self.subscribed_symbols if s in self.candle_data and len(self.candle_data[s]) >= self.min_data_points])
        }
        
    def add_symbol(self, symbol):
        """Add new symbol to monitoring"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.add(symbol)
            self.candle_data[symbol] = []
            self.last_signals[symbol] = {'signal': 0, 'timestamp': None}
            print(f"Added {symbol} to monitoring")
            
            # Initialize historical data for new symbol
            self._initialize_single_symbol_data(symbol)
            
    def remove_symbol(self, symbol):
        """Remove symbol from monitoring"""
        if symbol in self.subscribed_symbols:
            self.subscribed_symbols.remove(symbol)
            if symbol in self.candle_data:
                del self.candle_data[symbol]
            if symbol in self.last_signals:
                del self.last_signals[symbol]
            print(f"Removed {symbol} from monitoring")
    
    def _initialize_single_symbol_data(self, symbol):
        """Initialize historical data for a single symbol"""
        try:
            from datetime import timedelta
            end_date = datetime.now()
            days_needed = self._get_days_for_timeframe(self.timeframe, 250)
            start_date = end_date - timedelta(days=days_needed)
            
            df = self.binance_service.get_klines(
                symbol, self.timeframe,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            if not df.empty:
                candles = []
                for timestamp, row in df.iterrows():
                    candles.append({
                        'timestamp': timestamp,
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': float(row['volume'])
                    })
                
                self.candle_data[symbol] = candles[-250:]
                print(f"Initialized {symbol} with {len(self.candle_data[symbol])} historical candles")
                
        except Exception as e:
            print(f"Error initializing data for {symbol}: {str(e)}")