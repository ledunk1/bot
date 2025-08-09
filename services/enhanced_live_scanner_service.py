import time
import threading
from datetime import datetime
from services.websocket_service import WebSocketService
from services.binance_service import BinanceService
from services.coin_settings_manager import CoinSettingsManager

class EnhancedLiveScannerService:
    def __init__(self, telegram_bot_token=None, telegram_chat_id=None, trading_service=None):
        # Use environment config if tokens not provided
        from config.env_config import EnvConfig
        env_config = EnvConfig()
        
        # Use provided tokens or fall back to env config
        bot_token = telegram_bot_token or env_config.TELEGRAM_BOT_TOKEN
        chat_id = telegram_chat_id or env_config.TELEGRAM_CHAT_ID
        
        print(f"🔧 Enhanced scanner initializing with bot_token: {bot_token[:10] if bot_token else 'None'}..., chat_id: {chat_id}")
        
        self.websocket_service = WebSocketService(bot_token, chat_id, trading_service)
        self.binance_service = BinanceService()
        self.settings_manager = CoinSettingsManager()
        self.trading_service = trading_service
        self.is_running = False
        self.scan_thread = None
        
        # Scanner settings
        self.timeframe = '1h'  # Default timeframe
        self.scan_all_symbols = True
        self.custom_symbols = []
        self.min_signal_strength = 0.3
        self.max_symbols = 50  # Limit to prevent overload
        
        # Apply coin-specific settings to WebSocket service
        self._apply_coin_settings_to_websocket()
        
        # Pass trading service to WebSocket service
        self.websocket_service.trading_service = trading_service
        
    def _apply_coin_settings_to_websocket(self):
        """Apply coin-specific settings to WebSocket service"""
        try:
            # Update WebSocket service to use coin-specific settings
            self.websocket_service.settings_manager = self.settings_manager
            print("✅ Coin-specific settings applied to WebSocket service")
        except Exception as e:
            print(f"⚠️ Warning: Could not apply coin settings to WebSocket: {str(e)}")
    
    def start_scanner(self, timeframe='1h', scan_all_symbols=True, custom_symbols=None):
        """Start enhanced live scanner with WebSocket"""
        if self.is_running:
            print("Enhanced scanner is already running")
            return
            
        print(f"Starting Enhanced Live Scanner with WebSocket (Timeframe: {timeframe})...")
        
        # Set timeframe
        self.timeframe = timeframe
        
        # Determine symbols to monitor
        if scan_all_symbols:
            symbols = self._get_top_symbols()
        else:
            symbols = custom_symbols or ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
            
        # Limit symbols to prevent overload
        symbols = symbols[:self.max_symbols]
        
        print(f"Monitoring {len(symbols)} symbols: {symbols[:10]}{'...' if len(symbols) > 10 else ''}")
        
        self.is_running = True
        
        # Start WebSocket service
        self.websocket_service.start_websocket(symbols, self.timeframe)
        
        # Start monitoring thread
        self.scan_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.scan_thread.start()
        
    def stop_scanner(self):
        """Stop enhanced live scanner"""
        print("Stopping Enhanced Live Scanner...")
        self.is_running = False
        
        # Stop WebSocket
        self.websocket_service.stop_websocket()
        
        if self.scan_thread:
            self.scan_thread.join(timeout=10)
            
    def _get_top_symbols(self):
        """Get top trading symbols by volume"""
        try:
            # Get all symbols
            all_symbols = self.binance_service.get_futures_symbols()
            
            # Extended list of popular symbols to ensure we have enough
            popular_symbols = [
                'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT',
                'LINKUSDT', 'AVAXUSDT', 'MATICUSDT', 'ATOMUSDT', 'NEARUSDT',
                'UNIUSDT', 'LTCUSDT', 'BCHUSDT', 'XLMUSDT', 'VETUSDT',
                'FILUSDT', 'TRXUSDT', 'ETCUSDT', 'XMRUSDT', 'EOSUSDT',
                'AAVEUSDT', 'MKRUSDT', 'COMPUSDT', 'YFIUSDT', 'SUSHIUSDT',
                'SNXUSDT', 'CRVUSDT', 'BALUSDT', '1INCHUSDT', 'ENJUSDT',
                'MANAUSDT', 'SANDUSDT', 'CHZUSDT', 'GALAUSDT', 'AXSUSDT',
                'FLOWUSDT', 'FTMUSDT', 'HBARUSDT', 'ICPUSDT', 'THETAUSDT',
                'ALGOUSDT', 'EGLDUSDT', 'ZILUSDT', 'KSMUSDT', 'WAVESUSDT',
                'OMGUSDT', 'QTUMUSDT', 'BATUSDT', 'ZRXUSDT', 'STORJUSDT',
                'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT',
                'WIFUSDT', 'BONKUSDT', 'FLOKIUSDT', 'ORDIUSDT', 'INJUSDT',
                'TIAUSDT', 'SUIUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT',
                'STXUSDT', 'RNDRUSDT', 'FETUSDT', 'AGIXUSDT', 'OCEANUSDT',
                'GRTUSDT', 'BANDUSDT', 'RLCUSDT', 'NUUSDT', 'CTSIUSDT',
                'SKLUSDT', 'ANKRUSDT', 'CHRUSDT', 'LITUSDT', 'MTLUSDT',
                'OGNUSDT', 'NKNUSDT', 'SCUSDT', 'DGBUSDT', 'BTTUSDT',
                'HOTUSDT', 'IOTXUSDT', 'ONEUSDT', 'ICXUSDT', 'ONTUSDT',
                'ZECUSDT', 'DASHUSDT', 'XTZUSDT', 'RVNUSDT', 'DCRUSDT',
                'CELRUSDT', 'CTKUSDT', 'AKROUSDT', 'AXSUSDT', 'RAYUSDT',
                'C98USDT', 'MASKUSDT', 'ATAUSDT', 'GTCUSDT', 'TORNUSDT',
                'KEEPUSDT', 'ERNUSDT', 'KLAYUSDT', 'PHAUSDT', 'BONDUSDT',
                'MLNUSDT', 'DEXEUSDT', 'TCUSDT', 'PUNDIXUSDT', 'TLMUSDT',
                'MIRRUSDT', 'BARUSDT', 'FORTHUSDT', 'BAKEUSDT', 'BURGERUSDT',
                'SLPUSDT', 'SXPUSDT', 'CFXUSDT', 'TRUUSDT', 'LPTUSDT',
                'PSGUSDT', 'JUVUSDT', 'ASRUSDT', 'OGUSDT', 'ATMUSDT',
                'TKOUSDT', 'AMPUSDT', 'REQUSDT', 'WAXPUSDT', 'TRIBEUSDT',
                'GNOUSDT', 'XECUSDT', 'ELFUSDT', 'DYDXUSDT', 'POLYXUSDT',
                'IDEXUSDT', 'VIDTUSDT', 'USDPUSDT', 'GALAUSDT', 'ILVUSDT',
                'YGGUSDT', 'SYSUSDT', 'DFUSDT', 'FIDAUSDT', 'FRONTUSDT',
                'CVPUSDT', 'AGLDUSDT', 'RADUSDT', 'BETAUSDT', 'RAREUSDT',
                'LAZIOUSDT', 'CHESSUSDT', 'ADXUSDT', 'AUCTIONUSDT', 'DARUSDT',
                'BNXUSDT', 'RGTUSDT', 'MOVRUSDT', 'CITYUSDT', 'ENSUSDT',
                'KP3RUSDT', 'QIUSDT', 'PORTOUSDT', 'POWRUSDT', 'VGXUSDT',
                'JASMYUSDT', 'AMPUSDT', 'PLAUSDT', 'PYRUSDT', 'RNDRUSDT',
                'ALCXUSDT', 'SANTOSUSDT', 'MCUSDT', 'ANYUSDT', 'BICOUSDT',
                'FLUXUSDT', 'FXSUSDT', 'VOXELUSDT', 'HIGHUSDT', 'CVXUSDT',
                'PEOPLEUSDT', 'OOKIUSDT', 'SPELLUSDT', 'USTUSDT', 'JOEUSDT',
                'ACHUSDT', 'IMXUSDT', 'GLMRUSDT', 'LOKAUSDT', 'SCRTUSDT'
            ]
            
            # Filter to only include symbols that exist
            available_symbols = {s['symbol'] for s in all_symbols}
            filtered_symbols = [s for s in popular_symbols if s in available_symbols]
            
            # Ensure we have enough symbols
            if len(filtered_symbols) < self.max_symbols:
                # Add more symbols from available list if needed
                remaining_symbols = [s['symbol'] for s in all_symbols 
                                   if s['symbol'] not in filtered_symbols 
                                   and s['symbol'].endswith('USDT')]
                filtered_symbols.extend(remaining_symbols[:self.max_symbols - len(filtered_symbols)])
            
            result_symbols = filtered_symbols[:self.max_symbols]
            print(f"📊 Selected {len(result_symbols)} symbols for monitoring (max: {self.max_symbols})")
            
            return result_symbols
            
        except Exception as e:
            print(f"Error getting top symbols: {str(e)}")
            # Return default symbols
            return ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
            
    def _monitor_loop(self):
        """Monitor WebSocket service status"""
        consecutive_disconnects = 0
        max_consecutive_disconnects = 3
        
        while self.is_running:
            try:
                # Check WebSocket status
                if not self.websocket_service.is_running:
                    consecutive_disconnects += 1
                    print(f"WebSocket disconnected ({consecutive_disconnects}/{max_consecutive_disconnects})")
                    
                    if consecutive_disconnects >= max_consecutive_disconnects:
                        print("Multiple consecutive disconnects detected, restarting WebSocket service...")
                        try:
                            # Stop and restart WebSocket service
                            self.websocket_service.stop_websocket()
                            time.sleep(10)  # Wait 10 seconds before restart
                            
                            if self.is_running:  # Check if scanner is still running
                                symbols = list(self.websocket_service.subscribed_symbols)
                                self.websocket_service.start_websocket(symbols, self.timeframe)
                                consecutive_disconnects = 0
                                print("WebSocket service restarted successfully")
                        except Exception as e:
                            print(f"Error restarting WebSocket service: {str(e)}")
                            consecutive_disconnects = 0  # Reset counter to avoid infinite restart attempts
                else:
                    consecutive_disconnects = 0  # Reset counter on successful connection
                    
                # Print status every 5 minutes
                time.sleep(300)  # 5 minutes
                if self.is_running:
                    symbols_count = len(self.websocket_service.subscribed_symbols)
                    status = "Connected" if self.websocket_service.is_running else "Disconnected"
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring {symbols_count} symbols via WebSocket ({status})")
                    
            except Exception as e:
                print(f"Error in monitor loop: {str(e)}")
                time.sleep(60)
                
    def get_status(self):
        """Get scanner status"""
        # Get WebSocket health info
        health_info = self.websocket_service.get_connection_health()
        
        return {
            'is_running': self.is_running,
            'websocket_running': self.websocket_service.is_running,
            'connection_stable': health_info['is_stable'],
            'time_since_last_message': health_info['time_since_last_message'],
            'signal_buffer_size': health_info['signal_buffer_size'],
            'symbols_with_data': health_info['symbols_with_data'],
            'timeframe': self.timeframe,
            'symbols_count': len(self.websocket_service.subscribed_symbols),
            'monitored_symbols': list(self.websocket_service.subscribed_symbols),
            'min_signal_strength': self.min_signal_strength,
            'reconnect_attempts': health_info['reconnect_attempts']
        }
        
    def update_settings(self, min_signal_strength=None, max_symbols=None, timeframe=None):
        """Update scanner settings"""
        if min_signal_strength is not None:
            self.min_signal_strength = max(0.1, min(1.0, min_signal_strength))
            
        if max_symbols is not None:
            self.max_symbols = max(10, min(100, max_symbols))
            
        if timeframe is not None:
            self.timeframe = timeframe
            # Update WebSocket service timeframe if running
            if self.websocket_service.is_running:
                print(f"Timeframe updated to {timeframe}, restart scanner to apply changes")
            
        print(f"Scanner settings updated: min_strength={self.min_signal_strength}, max_symbols={self.max_symbols}, timeframe={self.timeframe}")
        
    def add_symbol(self, symbol):
        """Add symbol to monitoring"""
        if len(self.websocket_service.subscribed_symbols) < self.max_symbols:
            self.websocket_service.add_symbol(symbol)
            return True
        else:
            print(f"Cannot add {symbol}: Maximum symbols limit reached ({self.max_symbols})")
            return False
            
    def remove_symbol(self, symbol):
        """Remove symbol from monitoring"""
        self.websocket_service.remove_symbol(symbol)
        
    def get_live_data(self, symbol=None):
        """Get live data for symbol(s)"""
        if symbol:
            return self.websocket_service.get_live_data(symbol)
        else:
            return self.websocket_service.get_all_symbols_data()