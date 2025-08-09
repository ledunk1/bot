import json
import threading
import time
from datetime import datetime
from services.telegram.base_telegram import BaseTelegramService
from services.telegram.chart_generator import TelegramChartGenerator
from services.telegram.message_formatter import TelegramMessageFormatter
from services.telegram.entry_tracker import TelegramEntryTracker
from services.binance_trading_service import BinanceTradingService

class TelegramService(BaseTelegramService):
    """Main Telegram service combining all functionality"""
    
    def __init__(self, bot_token=None, chat_id=None, trading_service=None):
        super().__init__(bot_token, chat_id)
        
        # Initialize components
        self.chart_generator = TelegramChartGenerator()
        self.message_formatter = TelegramMessageFormatter()
        self.entry_tracker = TelegramEntryTracker(self, trading_service)
        
        # Trading service
        self.trading_service = trading_service
        
        # Start callback processing thread
        self._start_callback_processor()
    
    def _start_callback_processor(self):
        """Start background thread to process callbacks"""
        def callback_processor():
            while True:
                try:
                    self._process_callback_updates()
                    time.sleep(1)  # Check every second
                except Exception as e:
                    print(f"Callback processor error: {str(e)}")
                    time.sleep(5)
        
        callback_thread = threading.Thread(target=callback_processor, daemon=True)
        callback_thread.start()
        print("✅ Callback processor started")
    
    def _get_historical_winrate(self, symbol, timeframe):
        """Get historical win rate for symbol from Jan 1 current year to now"""
        try:
            from services.binance_service import BinanceService
            from services.indicator_service import IndicatorService
            from services.futures_backtest_service import FuturesBacktestService
            
            # Auto detect current year
            current_date = datetime.now()
            start_date = datetime(current_date.year, 1, 1)  # Jan 1 current year
            end_date = current_date
            
            print(f"Calculating win rate for {symbol} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            # Initialize services
            binance_service = BinanceService()
            indicator_service = IndicatorService()
            backtest_service = FuturesBacktestService()
            
            # Get historical data
            df = binance_service.get_klines(
                symbol, timeframe,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            if df.empty or len(df) < 200:
                return None
            
            # Calculate indicators and signals
            strategy_params = {
                'macd_fast': 14,
                'macd_slow': 32,
                'macd_signal': 10,
                'sma_length': 150
            }
            
            df_with_indicators = indicator_service.calculate_indicators(df, strategy_params)
            signals = indicator_service.generate_signals(df_with_indicators, strategy_params)
            
            # Run quick backtest to get win rate
            tp_sl_params = {
                'tp_base': 0.75,
                'stop_loss': 1.50,
                'max_tps': 5,
                'tp_close': 25
            }
            
            backtest_results = backtest_service.run_backtest(
                df_with_indicators, signals, 10000, 10, 10, tp_sl_params
            )
            
            stats = backtest_results['statistics']
            
            return {
                'win_rate': stats['win_rate'],
                'total_trades': stats['total_trades'],
                'total_return': stats['total_return'],
                'total_pnl': stats['total_pnl'],
                'period_days': (end_date - start_date).days,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            print(f"Error calculating historical win rate for {symbol}: {str(e)}")
            return None
    
    def send_enhanced_signal_notification(self, signal_data):
        """Send enhanced signal notification with Entry button"""
        try:
            print(f"📤 Preparing enhanced signal notification for {signal_data['symbol']}")
            
            # Get historical win rate info
            symbol = signal_data['symbol']
            timeframe = signal_data.get('timeframe', '1H')
            
            print(f"Getting historical win rate for {symbol} ({timeframe})...")
            historical_stats = self._get_historical_winrate(symbol, timeframe.lower())
            
            # Check if this signal has auto trade info
            auto_trade_info = ""
            if signal_data.get('auto_trade_executed'):
                auto_trade_info = f"\n\n🤖 **AUTO TRADE EXECUTED**\n{signal_data.get('auto_trade_result', '')}"
                if signal_data.get('trade_action'):
                    auto_trade_info += f"\n📊 **Action:** {signal_data['trade_action']}"
            
            # Create enhanced message with Entry button
            print(f"Formatting message for {symbol}...")
            message = self.message_formatter.format_enhanced_signal_message(signal_data, historical_stats)
            
            # Add auto trade info if available
            if auto_trade_info:
                message += auto_trade_info
            
            # Create inline keyboard with Entry and Auto Trade buttons
            buttons = [{
                "text": f"📈 ENTRY {signal_data['symbol']}",
                "callback_data": f"entry_{signal_data['symbol']}_{signal_data['signal']}_{signal_data['entry_price']}"
            }]
            
            # Enhanced button logic for auto trading
            if self.trading_service and self.trading_service.is_connected:
                # Check if we have existing position
                has_existing_position = (symbol in self.trading_service.active_positions and 
                                       self.trading_service.active_positions[symbol]['is_active'])
                
                if has_existing_position:
                    existing_side = self.trading_service.active_positions[symbol]['side']
                    new_signal_side = signal_data['signal']
                    
                    # If opposite signal, show close button instead
                    if ((existing_side == 'BUY' and new_signal_side == 'SELL') or 
                        (existing_side == 'SELL' and new_signal_side == 'BUY')):
                        buttons.append({
                            "text": f"🔄 CLOSE {existing_side} → OPEN {new_signal_side}",
                            "callback_data": f"auto_trade_{signal_data['symbol']}_{signal_data['signal']}_{signal_data['entry_price']}"
                        })
                else:
                    # No existing position - show normal auto trade button
                    if self.trading_service.trading_settings['auto_trading']['enabled']:
                        buttons.append({
                            "text": f"🤖 AUTO TRADE {signal_data['symbol']}",
                            "callback_data": f"auto_trade_{signal_data['symbol']}_{signal_data['signal']}_{signal_data['entry_price']}"
                        })
                
                # Always show manual trade button if enabled
                if self.trading_service.trading_settings['manual_trading']['enabled']:
                    buttons.append({
                        "text": f"💰 LIVE TRADE {signal_data['symbol']}",
                        "callback_data": f"live_trade_{signal_data['symbol']}_{signal_data['signal']}_{signal_data['entry_price']}"
                    })
            
            keyboard = {
                "inline_keyboard": [[
                    button for button in buttons
                ]]
            }
            
            # Enhanced auto trading check - only for new positions, not opposite signals
            print(f"Checking auto trading for {symbol}...")
            if (not signal_data.get('auto_trade_executed') and  # Don't double-execute
                self.trading_service and 
                self.trading_service.is_connected and 
                self.trading_service.trading_settings['auto_trading']['enabled'] and
                not signal_data.get('is_opposite_signal')):  # Opposite signals already handled above
                
                # Try auto trade
                success, result = self.trading_service.execute_auto_trade(
                    signal_data['symbol'], 
                    signal_data['signal'], 
                    signal_data['entry_price'], 
                    signal_data
                )
                
                if success:
                    # Add auto trade confirmation to message
                    message += f"\n\n🤖 **AUTO TRADE EXECUTED**\n{result}"
                else:
                    # Add auto trade skip reason
                    message += f"\n\n⏭️ **Auto Trade Skipped:** {result}"
            
            # Disable reply keyboard and notifications for broadcast
            extra_params = {
                'disable_notification': False,
                'protect_content': True,
                'disable_web_page_preview': True,
                'reply_markup': json.dumps(keyboard)
            }
            
            # Send message with image and button
            print(f"Sending Telegram notification for {symbol}...")
            result = self._send_message(message, extra_params)
            
            if result and result.get('ok'):
                print(f"✅ Enhanced signal notification sent successfully for {symbol}")
                return True
            else:
                print(f"❌ Failed to send enhanced signal notification for {symbol}")
                return False
            
        except Exception as e:
            print(f"Error sending enhanced telegram notification: {str(e)}")
            return False
    
    def send_signal_notification(self, signal_data):
        """Send signal notification with chart image"""
        try:
            # Get historical win rate info
            symbol = signal_data['symbol']
            timeframe = signal_data.get('timeframe', '1H')
            
            print(f"Getting historical win rate for {symbol} ({timeframe})...")
            historical_stats = self._get_historical_winrate(symbol, timeframe.lower())
            
            # Create message
            message = self.message_formatter.format_signal_message(signal_data, historical_stats)
            
            # Create Entry button
            keyboard = {
                "inline_keyboard": [[
                    {
                        "text": f"📈 ENTRY {signal_data['symbol']}",
                        "callback_data": f"entry_{signal_data['symbol']}_{signal_data['signal']}_{signal_data['price']}"
                    }
                ]]
            }
            
            # Broadcast mode parameters
            extra_params = {
                'disable_notification': False,
                'protect_content': True,
                'disable_web_page_preview': True,
                'reply_markup': json.dumps(keyboard)
            }
            
            # Send message with image
            self._send_message(message, extra_params)
                
            return True
            
        except Exception as e:
            print(f"Error sending telegram notification: {str(e)}")
            return False
    
    def handle_entry_callback(self, symbol, signal_type, entry_price):
        """Handle entry button callback"""
        return self.entry_tracker.handle_entry_callback(symbol, signal_type, entry_price)
    
    def handle_done_callback(self, symbol):
        """Handle done button callback"""
        return self.entry_tracker.handle_done_callback(symbol)
    
    def get_active_entries_status(self):
        """Get active entry tracking status"""
        return self.entry_tracker.get_active_entries_status()
    
    def handle_live_trade_callback(self, symbol, signal_type, entry_price):
        """Handle live trade button callback"""
        return self.entry_tracker.handle_live_trade_callback(symbol, signal_type, entry_price)
    
    def handle_auto_trade_callback(self, symbol, signal_type, entry_price):
        """Handle auto trade button callback"""
        return self.entry_tracker.handle_auto_trade_callback(symbol, signal_type, entry_price)