from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime
import pandas as pd
import json
import os
from config.env_config import EnvConfig

from services.binance_service import BinanceService
from services.indicator_service import IndicatorService
from services.futures_backtest_service import FuturesBacktestService
from services.live_data_service import LiveDataService
from services.enhanced_live_scanner_service import EnhancedLiveScannerService
from services.websocket_service import WebSocketService
from services.telegram_service import TelegramService
from services.optimizer_service import OptimizerService
from services.coin_settings_manager import CoinSettingsManager
from services.per_coin_optimizer import PerCoinOptimizer
from services.binance_trading_service import BinanceTradingService
from utils.date_utils import validate_date_range

app = Flask(__name__)
CORS(app)

# Load environment configuration
env_config = EnvConfig()

# Initialize services
binance_service = BinanceService()
indicator_service = IndicatorService()
backtest_service = FuturesBacktestService()
live_data_service = LiveDataService()
enhanced_scanner_service = None  # Will be initialized when needed
websocket_service = None  # Will be initialized when needed

# Initialize trading service
# Initialize trading service with .env auto-configuration
trading_service = BinanceTradingService()

# Initialize telegram service with trading service
telegram_service = TelegramService(trading_service=trading_service)

optimizer_service = OptimizerService()
coin_settings_manager = CoinSettingsManager()
per_coin_optimizer = PerCoinOptimizer()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/live')
def live():
    return render_template('live.html')

@app.route('/optimizer')
def optimizer():
    return render_template('optimizer.html')

@app.route('/api/symbols')
def get_symbols():
    """Get available trading symbols from Binance"""
    try:
        symbols = binance_service.get_futures_symbols()
        return jsonify({'success': True, 'data': symbols})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/klines', methods=['POST'])
def get_klines():
    """Get candlestick data for specified symbol and date range"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        interval = data.get('interval', '1h')
        
        # Validate inputs
        if not all([symbol, start_date, end_date]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        
        if not validate_date_range(start_date, end_date):
            return jsonify({'success': False, 'error': 'Invalid date range'}), 400
        
        print(f"Requesting data for {symbol} from {start_date} to {end_date} with interval {interval}")
        
        # Get candlestick data
        klines = binance_service.get_klines(symbol, interval, start_date, end_date)
        print(f"Successfully retrieved {len(klines)} data points")
        
        return jsonify({'success': True, 'data': klines})
    except Exception as e:
        print(f"Error in get_klines endpoint: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    """Run backtest with specified parameters"""
    try:
        data = request.get_json()
        
        # Extract parameters
        symbol = data.get('symbol')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        interval = data.get('interval', '1h')
        leverage = float(data.get('leverage', 1))
        margin = float(data.get('margin', 1000))
        balance = float(data.get('balance', 10000))
        
        # Strategy settings
        macd_fast = int(data.get('macd_fast', 12))
        macd_slow = int(data.get('macd_slow', 26))
        macd_signal = int(data.get('macd_signal', 9))
        sma_length = int(data.get('sma_length', 200))
        
        # TP/SL settings
        tp_base = float(data.get('tp_base', 0.75))
        stop_loss = float(data.get('stop_loss', 1.50))
        max_tps = int(data.get('max_tps', 10))
        tp_close = float(data.get('tp_close', 25))
        
        # Validate inputs
        if not all([symbol, start_date, end_date]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        
        print(f"Running backtest for {symbol} from {start_date} to {end_date}")
        
        # Get market data
        klines = binance_service.get_klines(symbol, interval, start_date, end_date)
        print(f"Retrieved {len(klines)} data points")
        
        # Get coin-specific settings
        coin_settings = coin_settings_manager.load_coin_settings(symbol)
        
        # Use coin-specific strategy parameters if available
        if coin_settings.get('optimization_score', 0) > 0:
            strategy_params = coin_settings['strategy_params']
            tp_sl_params = coin_settings['tp_sl_params']
            print(f"Using optimized settings for {symbol} (Score: {coin_settings['optimization_score']:.2f})")
        else:
            # Use parameters from request
            strategy_params = {
                'macd_fast': macd_fast,
                'macd_slow': macd_slow,
                'macd_signal': macd_signal,
                'sma_length': sma_length
            }
            tp_sl_params = {
                'tp_base': tp_base,
                'stop_loss': stop_loss,
                'max_tps': max_tps,
                'tp_close': tp_close
            }
            print(f"Using default/manual settings for {symbol}")
        
        # Verify data range
        if not klines.empty:
            print(f"Market data range: {klines.index.min()} to {klines.index.max()}")
            
            # Check if we have enough data
            expected_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days
            actual_days = (klines.index.max() - klines.index.min()).days
            print(f"Expected {expected_days} days, got {actual_days} days of data")
        
        df = indicator_service.calculate_indicators(klines, strategy_params)
        print("Calculated indicators")
        print(f"Indicators calculated: {list(df.columns)}")
        
        # Verify indicators data range
        if not df.empty:
            print(f"Indicators data range: {df.index.min()} to {df.index.max()}")
        
        signals = indicator_service.generate_signals(df, strategy_params)
        print(f"Generated {len(signals[signals['signal'] != 0])} signals")
        
        # Get strategy info for logging
        strategy_info = indicator_service.get_strategy_info()
        print(f"Using strategy: {strategy_info['name']}")
        
        # Run backtest
        backtest_results = backtest_service.run_backtest(
            df, signals, balance, leverage, margin, tp_sl_params
        )
        print("Completed backtest")
        
        # Print backtest summary
        print(f"Backtest completed with {backtest_results['statistics']['total_trades']} total trades")
        if backtest_results['trades']:
            first_trade = backtest_results['trades'][0]['entry_time']
            last_trade = backtest_results['trades'][-1]['exit_time']
            print(f"Trade period: {first_trade} to {last_trade}")
        
        # Prepare chart data
        chart_data = backtest_service.prepare_chart_data(df, signals)
        
        return jsonify({
            'success': True,
            'data': {
                'results': backtest_results,
                'chart_data': chart_data,
                'signals': signals.to_dict('records')
            }
        })
    except Exception as e:
        print(f"Backtest error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/live-data', methods=['POST'])
def get_live_data():
    """Get live data for chart"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', 'BTCUSDT')
        interval = data.get('interval', '1h')
        limit = data.get('limit', 100)
        
        result = live_data_service.get_live_data(symbol, interval, limit)
        
        if result:
            return jsonify({'success': True, 'data': result})
        else:
            return jsonify({'success': False, 'error': 'No data available'}), 404
            
    except Exception as e:
        print(f"Live data error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scanner/start', methods=['POST'])
def start_scanner():
    """Start the enhanced live scanner with WebSocket"""
    try:
        global enhanced_scanner_service
        
        data = request.get_json()
        
        # Always use .env config for consistency
        bot_token = env_config.TELEGRAM_BOT_TOKEN
        chat_id = env_config.TELEGRAM_CHAT_ID
        
        # Only use manual input if .env is not configured
        if not bot_token or bot_token == '' or bot_token == 'YOUR_BOT_TOKEN':
            bot_token = data.get('telegram_bot_token', '').strip()
        
        if not chat_id or chat_id == '' or chat_id == 'YOUR_CHAT_ID':
            chat_id = data.get('telegram_chat_id', '').strip()
        
        timeframe = data.get('timeframe', '1h')
        
        scan_all_symbols = data.get('scan_all_symbols', True)
        custom_symbols = data.get('custom_symbols', [])
        
        print(f"🔍 Starting scanner with bot_token: {bot_token[:10] if bot_token else 'None'}..., chat_id: {chat_id}")
        
        # Validate Telegram configuration
        if not bot_token or not chat_id:
            is_valid, message = env_config.validate_telegram_config()
            if not is_valid:
                return jsonify({'success': False, 'error': message}), 400
        
        if enhanced_scanner_service and enhanced_scanner_service.is_running:
            return jsonify({'success': False, 'error': 'Scanner is already running'})
        
        enhanced_scanner_service = EnhancedLiveScannerService(bot_token, chat_id, trading_service)
        enhanced_scanner_service.start_scanner(timeframe, scan_all_symbols, custom_symbols)
        
        return jsonify({'success': True, 'message': 'Enhanced WebSocket scanner started successfully'})
        
    except Exception as e:
        print(f"Scanner start error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scanner/stop', methods=['POST'])
def stop_scanner():
    """Stop the enhanced live scanner"""
    try:
        global enhanced_scanner_service
        
        if enhanced_scanner_service:
            enhanced_scanner_service.stop_scanner()
            enhanced_scanner_service = None
        
        return jsonify({'success': True, 'message': 'Scanner stopped successfully'})
        
    except Exception as e:
        print(f"Scanner stop error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scanner/status')
def get_scanner_status():
    """Get scanner status"""
    try:
        global enhanced_scanner_service
        
        if enhanced_scanner_service:
            status = enhanced_scanner_service.get_status()
            return jsonify({'success': True, 'status': status})
        else:
            return jsonify({'success': True, 'status': {'is_running': False, 'websocket_running': False}})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/websocket/start', methods=['POST'])
def start_websocket():
    """Start WebSocket service for live data"""
    try:
        global websocket_service
        
        data = request.get_json()
        symbols = data.get('symbols', ['BTCUSDT', 'ETHUSDT'])
        
        # Use .env config if not provided in request
        bot_token = data.get('telegram_bot_token') or env_config.TELEGRAM_BOT_TOKEN
        chat_id = data.get('telegram_chat_id') or env_config.TELEGRAM_CHAT_ID
        
        if websocket_service and websocket_service.is_running:
            return jsonify({'success': False, 'error': 'WebSocket is already running'})
        
        websocket_service = WebSocketService(bot_token, chat_id)
        websocket_service.start_websocket(symbols)
        
        return jsonify({'success': True, 'message': f'WebSocket started for {len(symbols)} symbols'})
        
    except Exception as e:
        print(f"WebSocket start error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/websocket/stop', methods=['POST'])
def stop_websocket():
    """Stop WebSocket service"""
    try:
        global websocket_service
        
        if websocket_service:
            websocket_service.stop_websocket()
            websocket_service = None
        
        return jsonify({'success': True, 'message': 'WebSocket stopped successfully'})
        
    except Exception as e:
        print(f"WebSocket stop error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/websocket/data/<symbol>')
def get_websocket_data(symbol):
    """Get live WebSocket data for symbol"""
    try:
        global websocket_service
        
        if not websocket_service or not websocket_service.is_running:
            return jsonify({'success': False, 'error': 'WebSocket not running'}), 400
        
        data = websocket_service.get_live_data(symbol)
        
        if data:
            return jsonify({'success': True, 'data': data})
        else:
            return jsonify({'success': False, 'error': 'No data available for symbol'}), 404
            
    except Exception as e:
        print(f"WebSocket data error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scanner/symbols', methods=['POST'])
def manage_scanner_symbols():
    """Add or remove symbols from scanner"""
    try:
        global enhanced_scanner_service
        
        if not enhanced_scanner_service:
            return jsonify({'success': False, 'error': 'Scanner not running'}), 400
        
        data = request.get_json()
        action = data.get('action')  # 'add' or 'remove'
        symbol = data.get('symbol')
        
        if action == 'add':
            success = enhanced_scanner_service.add_symbol(symbol)
            if success:
                return jsonify({'success': True, 'message': f'Added {symbol} to monitoring'})
            else:
                return jsonify({'success': False, 'error': 'Failed to add symbol (limit reached?)'})
        elif action == 'remove':
            enhanced_scanner_service.remove_symbol(symbol)
            return jsonify({'success': True, 'message': f'Removed {symbol} from monitoring'})
        else:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scanner/settings', methods=['POST'])
def update_scanner_settings():
    """Update scanner settings"""
    try:
        global enhanced_scanner_service
        
        data = request.get_json()
        min_signal_strength = data.get('min_signal_strength')
        max_symbols = data.get('max_symbols')
        timeframe = data.get('timeframe')
        
        if enhanced_scanner_service:
            enhanced_scanner_service.update_settings(min_signal_strength, max_symbols, timeframe)
        
        return jsonify({'success': True, 'message': 'Settings updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/telegram/test', methods=['POST'])
def test_telegram():
    """Test telegram connection"""
    try:
        data = request.get_json()
        
        # Always use .env config for consistency
        bot_token = env_config.TELEGRAM_BOT_TOKEN
        chat_id = env_config.TELEGRAM_CHAT_ID
        
        # Only use manual input if .env is not configured
        if not bot_token or bot_token == '' or bot_token == 'YOUR_BOT_TOKEN':
            bot_token = data.get('bot_token', '').strip()
        
        if not chat_id or chat_id == '' or chat_id == 'YOUR_CHAT_ID':
            chat_id = data.get('chat_id', '').strip()
        
        print(f"🔍 Testing Telegram with bot_token: {bot_token[:10] if bot_token else 'None'}..., chat_id: {chat_id}")
        
        if not bot_token or bot_token == '' or bot_token == 'YOUR_BOT_TOKEN':
            return jsonify({'success': False, 'error': 'Bot token not configured. Get it from @BotFather on Telegram'}), 400
        
        if not chat_id or chat_id == '' or chat_id == 'YOUR_CHAT_ID':
            return jsonify({'success': False, 'error': 'Chat ID not configured. Get it from @userinfobot on Telegram'}), 400
        
        # Additional validation
        if ':' not in bot_token or len(bot_token) < 35:
            return jsonify({'success': False, 'error': 'Invalid bot token format. Should be like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz'}), 400
        
        try:
            int(chat_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Chat ID must be a number. Get it from @userinfobot'}), 400
        
        # Check env config validation if using env values
        if not data.get('bot_token') and not data.get('chat_id'):
            is_valid, message = env_config.validate_telegram_config()
            if not is_valid:
                return jsonify({'success': False, 'error': message}), 400
        
        test_service = TelegramService(bot_token, chat_id)
        success = test_service.test_connection()
        
        if success:
            return jsonify({'success': True, 'message': 'Connection successful'})
        else:
            return jsonify({'success': False, 'error': 'Connection failed. Check bot token, chat ID, and make sure bot is added to the chat'}), 400
            
    except Exception as e:
        print(f"Error in telegram test endpoint: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/telegram/broadcast-mode', methods=['POST'])
def configure_broadcast_mode():
    """Configure bot for broadcast mode"""
    try:
        data = request.get_json()
        
        # Always use .env config for consistency
        bot_token = env_config.TELEGRAM_BOT_TOKEN
        chat_id = env_config.TELEGRAM_CHAT_ID
        
        # Only use manual input if .env is not configured
        if not bot_token or bot_token == '' or bot_token == 'YOUR_BOT_TOKEN':
            bot_token = data.get('bot_token', '').strip()
        
        if not chat_id or chat_id == '' or chat_id == 'YOUR_CHAT_ID':
            chat_id = data.get('chat_id', '').strip()
        
        print(f"🔍 Configuring broadcast mode with bot_token: {bot_token[:10] if bot_token else 'None'}..., chat_id: {chat_id}")
        
        if not bot_token or not chat_id:
            is_valid, message = env_config.validate_telegram_config()
            if not is_valid:
                return jsonify({'success': False, 'error': message}), 400
        
        broadcast_service = TelegramService(bot_token, chat_id, trading_service)
        
        # Configure broadcast mode
        broadcast_service._configure_broadcast_mode()
        broadcast_service.set_bot_description()
        
        # Send configuration confirmation
        config_message = """
🤖 **BOT CONFIGURED FOR ENHANCED BROADCAST MODE**

✅ **Settings Applied:**
• Webhook disabled
• Commands removed  
• Broadcast mode enabled
• Auto-reply disabled
• Interactive TP/SL tracking enabled

📢 **Enhanced Features:**
• 📈 Entry buttons for TP/SL tracking
• 🎯 Real-time TP/SL notifications
• ✅ Done buttons to stop tracking
• 📊 Interactive signal management
        """
        
        broadcast_service._send_message(config_message.strip())
        
        return jsonify({'success': True, 'message': 'Bot configured for enhanced broadcast mode successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/telegram/entry-callback', methods=['POST'])
def handle_entry_callback():
    """Handle entry button callback"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        signal_type = data.get('signal_type')
        entry_price = data.get('entry_price')
        
        # Use .env config if not provided in request
        bot_token = data.get('bot_token') or env_config.TELEGRAM_BOT_TOKEN
        chat_id = data.get('chat_id') or env_config.TELEGRAM_CHAT_ID
        
        if not bot_token or not chat_id:
            is_valid, message = env_config.validate_telegram_config()
            if not is_valid:
                return jsonify({'success': False, 'error': message}), 400
        
        telegram_service = TelegramService(bot_token, chat_id)
        success = telegram_service.handle_entry_callback(symbol, signal_type, entry_price)
        
        if success:
            return jsonify({'success': True, 'message': f'Entry tracking started for {symbol}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to start entry tracking'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/telegram/done-callback', methods=['POST'])
def handle_done_callback():
    """Handle done button callback"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        
        # Use .env config if not provided in request
        bot_token = data.get('bot_token') or env_config.TELEGRAM_BOT_TOKEN
        chat_id = data.get('chat_id') or env_config.TELEGRAM_CHAT_ID
        
        if not bot_token or not chat_id:
            is_valid, message = env_config.validate_telegram_config()
            if not is_valid:
                return jsonify({'success': False, 'error': message}), 400
        
        telegram_service = TelegramService(bot_token, chat_id)
        success = telegram_service.handle_done_callback(symbol)
        
        if success:
            return jsonify({'success': True, 'message': f'Entry tracking completed for {symbol}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to complete entry tracking'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/telegram/active-entries')
def get_active_entries():
    """Get active entry tracking status"""
    try:
        # Use .env config
        bot_token = env_config.TELEGRAM_BOT_TOKEN
        chat_id = env_config.TELEGRAM_CHAT_ID
        
        if not bot_token or not chat_id:
            is_valid, message = env_config.validate_telegram_config()
            if not is_valid:
                return jsonify({'success': False, 'error': message}), 400
        
        telegram_service = TelegramService(bot_token, chat_id)
        status = telegram_service.get_active_entries_status()
        
        return jsonify({'success': True, 'data': status})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/coin-settings/<symbol>')
def get_coin_settings(symbol):
    """Get settings for a specific coin"""
    try:
        settings = coin_settings_manager.load_coin_settings(symbol)
        return jsonify({'success': True, 'data': settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/coin-settings/<symbol>', methods=['POST'])
def save_coin_settings(symbol):
    """Save settings for a specific coin"""
    try:
        data = request.get_json()
        success = coin_settings_manager.save_coin_settings(symbol, data)
        
        if success:
            return jsonify({'success': True, 'message': f'Settings saved for {symbol}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to save settings'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/coin-settings/summary')
def get_settings_summary():
    """Get summary of all coin settings"""
    try:
        summary = coin_settings_manager.get_settings_summary()
        return jsonify({'success': True, 'data': summary})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/coin-settings/export', methods=['POST'])
def export_coin_settings():
    """Export coin settings to CSV"""
    try:
        filepath = coin_settings_manager.export_settings_csv()
        if filepath:
            return jsonify({'success': True, 'filepath': filepath})
        else:
            return jsonify({'success': False, 'error': 'Export failed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/coin-settings/import', methods=['POST'])
def import_coin_settings():
    """Import coin settings from CSV"""
    try:
        data = request.get_json()
        filepath = data.get('filepath')
        
        if not filepath:
            return jsonify({'success': False, 'error': 'Filepath required'}), 400
        
        success = coin_settings_manager.import_settings_csv(filepath)
        
        if success:
            return jsonify({'success': True, 'message': 'Settings imported successfully'})
        else:
            return jsonify({'success': False, 'error': 'Import failed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/per-coin-optimizer/start', methods=['POST'])
def start_per_coin_optimization():
    """Start per-coin optimization"""
    try:
        data = request.get_json()
        
        # Get symbols list
        symbols = data.get('symbols', [])
        symbol_selection = data.get('symbol_selection', 'top_50')  # New parameter
        
        if not symbols:
            # Auto-select symbols based on selection type
            if symbol_selection == 'all':
                # Get all available symbols
                all_symbols = per_coin_optimizer.get_all_available_symbols()
                symbols = all_symbols
                print(f"🔄 Auto-selected ALL {len(symbols)} available symbols for bulk optimization")
            elif symbol_selection == 'top_100':
                symbols = per_coin_optimizer.get_popular_symbols(100)
                print(f"🔄 Auto-selected top {len(symbols)} symbols for optimization")
            elif symbol_selection == 'top_50':
                symbols = per_coin_optimizer.get_popular_symbols(50)
                print(f"🔄 Auto-selected top {len(symbols)} symbols for optimization")
            elif symbol_selection == 'top_20':
                symbols = per_coin_optimizer.get_popular_symbols(20)
                print(f"🔄 Auto-selected top {len(symbols)} symbols for optimization")
            elif symbol_selection == 'top_10':
                symbols = per_coin_optimizer.get_popular_symbols(10)
                print(f"🔄 Auto-selected top {len(symbols)} symbols for optimization")
            else:
                # Default to top 10 (minimum recommended)
                symbols = per_coin_optimizer.get_popular_symbols(10)
                print(f"🔄 Auto-selected top {len(symbols)} symbols for optimization (default minimum)")
        
        # Ensure minimum 10 symbols for per-coin optimization
        if len(symbols) < 10:
            # Auto-expand to minimum 10 if less provided
            popular_symbols = per_coin_optimizer.get_popular_symbols(10)
            symbols = list(set(symbols + popular_symbols))[:10]
            print(f"⚠️ Expanded to minimum 10 symbols: {symbols}")
        
        # Enhanced logging for parallel processing
        max_workers = data.get('max_workers', 8)
        print(f"🚀 Starting per-coin optimization with enhanced parallel processing:")
        print(f"   📊 Symbols: {len(symbols)}")
        print(f"   ⚡ Max Workers: {max_workers}")
        print(f"   🔄 Parallel Data Fetching: Enabled")
        print(f"   📦 Batch Processing: Up to 20 symbols simultaneously")
        print(f"   ⏭️ Smart Skip: Enabled (will skip already optimized coins)")
        
        # Validate required parameters
        required_fields = ['param_ranges', 'trading_params']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Create optimization parameters template
        optimization_params = {
            'interval': data.get('interval', '1h'),
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
            'param_ranges': data['param_ranges'],
            'trading_params': data['trading_params'],
            'max_workers': max_workers
        }
        
        # Validate date range
        if not validate_date_range(optimization_params['start_date'], optimization_params['end_date']):
            return jsonify({'success': False, 'error': 'Invalid date range'}), 400
        
        # Start per-coin optimization
        success, message = per_coin_optimizer.start_per_coin_optimization(symbols, optimization_params)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400
            
    except Exception as e:
        print(f"Error starting per-coin optimization: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/per-coin-optimizer/start-force', methods=['POST'])
def start_per_coin_optimization_force():
    """Start per-coin optimization with force re-optimize"""
    try:
        data = request.get_json()
        
        # Get symbols list
        symbols = data.get('symbols', [])
        symbol_selection = data.get('symbol_selection', 'top_50')
        
        if not symbols:
            # Auto-select symbols based on selection type
            if symbol_selection == 'all':
                all_symbols = per_coin_optimizer.get_all_available_symbols()
                symbols = all_symbols
                print(f"🔄 Auto-selected ALL {len(symbols)} available symbols for FORCE optimization")
            elif symbol_selection == 'top_100':
                symbols = per_coin_optimizer.get_popular_symbols(100)
                print(f"🔄 Auto-selected top {len(symbols)} symbols for FORCE optimization")
            elif symbol_selection == 'top_50':
                symbols = per_coin_optimizer.get_popular_symbols(50)
                print(f"🔄 Auto-selected top {len(symbols)} symbols for FORCE optimization")
            elif symbol_selection == 'top_20':
                symbols = per_coin_optimizer.get_popular_symbols(20)
                print(f"🔄 Auto-selected top {len(symbols)} symbols for FORCE optimization")
            elif symbol_selection == 'top_10':
                symbols = per_coin_optimizer.get_popular_symbols(10)
                print(f"🔄 Auto-selected top {len(symbols)} symbols for FORCE optimization")
            else:
                symbols = per_coin_optimizer.get_popular_symbols(10)
                print(f"🔄 Auto-selected top {len(symbols)} symbols for FORCE optimization (default)")
        
        # Enhanced logging for force optimization
        max_workers = data.get('max_workers', 8)
        print(f"🚀 Starting FORCE per-coin optimization:")
        print(f"   📊 Symbols: {len(symbols)}")
        print(f"   ⚡ Max Workers: {max_workers}")
        print(f"   🔄 Force Mode: ALL coins will be re-optimized")
        print(f"   ⚠️ Existing results will be overwritten")
        
        # Validate required parameters
        required_fields = ['param_ranges', 'trading_params']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Create optimization parameters template
        optimization_params = {
            'interval': data.get('interval', '1h'),
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
            'param_ranges': data['param_ranges'],
            'trading_params': data['trading_params'],
            'max_workers': max_workers
        }
        
        # Validate date range
        if not validate_date_range(optimization_params['start_date'], optimization_params['end_date']):
            return jsonify({'success': False, 'error': 'Invalid date range'}), 400
        
        # Start force per-coin optimization
        success, message = per_coin_optimizer.start_per_coin_optimization_force(symbols, optimization_params)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400
            
    except Exception as e:
        print(f"Error starting force per-coin optimization: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/per-coin-optimizer/stop', methods=['POST'])
def stop_per_coin_optimization():
    """Stop per-coin optimization"""
    try:
        success = per_coin_optimizer.stop_optimization()
        
        if success:
            return jsonify({'success': True, 'message': 'Per-coin optimization stopped'})
        else:
            return jsonify({'success': False, 'error': 'No per-coin optimization running'})
            
    except Exception as e:
        print(f"Error stopping per-coin optimization: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/per-coin-optimizer/status')
def get_per_coin_optimization_status():
    """Get per-coin optimization status"""
    try:
        status = per_coin_optimizer.get_status()
        return jsonify({'success': True, 'data': status})
        
    except Exception as e:
        print(f"Error getting per-coin optimization status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/per-coin-optimizer/estimate', methods=['POST'])
def get_optimization_estimate():
    """Get optimization time estimate"""
    try:
        data = request.get_json()
        
        # Handle symbol selection
        symbols = data.get('symbols', [])
        symbol_selection = data.get('symbol_selection', 'top_50')
        
        if not symbols:
            if symbol_selection == 'all':
                symbols = per_coin_optimizer.get_all_available_symbols()
            elif symbol_selection == 'top_100':
                symbols = per_coin_optimizer.get_popular_symbols(100)
            elif symbol_selection == 'top_50':
                symbols = per_coin_optimizer.get_popular_symbols(50)
            elif symbol_selection == 'top_20':
                symbols = per_coin_optimizer.get_popular_symbols(20)
            else:
                symbols = per_coin_optimizer.get_popular_symbols(50)  # Default
        
        optimization_params = {
            'param_ranges': data.get('param_ranges', {}),
            'max_workers': data.get('max_workers', 4)
        }
        
        estimate = per_coin_optimizer.get_optimization_queue_estimate(symbols, optimization_params)
        return jsonify({'success': True, 'data': estimate})
        
    except Exception as e:
        print(f"Error getting optimization estimate: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/optimizer/start', methods=['POST'])
def start_optimization():
    """Start parameter optimization"""
    try:
        data = request.get_json()
        
        # Validate required parameters
        required_fields = ['symbol', 'start_date', 'end_date', 'param_ranges', 'trading_params']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Validate date range
        if not validate_date_range(data['start_date'], data['end_date']):
            return jsonify({'success': False, 'error': 'Invalid date range'}), 400
        
        # Start optimization
        success, message = optimizer_service.start_optimization(data)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400
            
    except Exception as e:
        print(f"Error starting optimization: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/optimizer/stop', methods=['POST'])
def stop_optimization():
    """Stop parameter optimization"""
    try:
        success = optimizer_service.stop_optimization()
        
        if success:
            return jsonify({'success': True, 'message': 'Optimization stopped'})
        else:
            return jsonify({'success': False, 'error': 'No optimization running'})
            
    except Exception as e:
        print(f"Error stopping optimization: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/optimizer/status')
def get_optimization_status():
    """Get optimization status and results"""
    try:
        status = optimizer_service.get_optimization_status()
        return jsonify({'success': True, 'data': status})
        
    except Exception as e:
        print(f"Error getting optimization status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/optimizer/cache')
def get_cache_info():
    """Get cached data information"""
    try:
        cached_files = optimizer_service.get_cached_files()
        return jsonify({'success': True, 'data': cached_files})
        
    except Exception as e:
        print(f"Error getting cache info: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/optimizer/cache/clear', methods=['POST'])
def clear_cache():
    """Clear cached data"""
    try:
        data = request.get_json() or {}
        older_than_hours = data.get('older_than_hours', 24)
        
        cleared_count = optimizer_service.clear_cache(older_than_hours)
        
        return jsonify({
            'success': True, 
            'message': f'Cleared {cleared_count} cached files',
            'cleared_count': cleared_count
        })
        
    except Exception as e:
        print(f"Error clearing cache: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/env/telegram')
def get_telegram_env():
    """Get Telegram configuration from environment"""
    try:
        print("Getting Telegram environment configuration...")
        config = env_config.get_telegram_config()
        
        # Better validation
        bot_token_valid = (config['bot_token'] and 
                          config['bot_token'] != '' and 
                          config['bot_token'] != 'YOUR_BOT_TOKEN' and
                          ':' in config['bot_token'])
        
        chat_id_valid = (config['chat_id'] and 
                        config['chat_id'] != '' and 
                        config['chat_id'] != 'YOUR_CHAT_ID')
        
        print(f"Telegram config loaded: bot_token_valid={bot_token_valid}, chat_id_valid={chat_id_valid}")
        
        # Don't expose full token, just indicate if it's configured
        return jsonify({
            'success': True,
            'data': {
                'bot_token_configured': bot_token_valid,
                'chat_id_configured': chat_id_valid,
                'bot_token_preview': config['bot_token'][:10] + '...' if bot_token_valid else 'Not configured',
                'chat_id': config['chat_id']
            }
        })
    except Exception as e:
        print(f"Error getting Telegram env config: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/env/binance')
def get_binance_env():
    """Get Binance API configuration from environment"""
    try:
        print("Getting Binance API environment configuration...")
        config = env_config.get_binance_config()
        
        # Better validation
        api_key_valid = (config['api_key'] and 
                        config['api_key'] != '' and 
                        len(config['api_key']) == 64)
        
        api_secret_valid = (config['api_secret'] and 
                           config['api_secret'] != '' and 
                           len(config['api_secret']) == 64)
        
        print(f"Binance config loaded: api_key_valid={api_key_valid}, api_secret_valid={api_secret_valid}")
        
        # Don't expose full credentials, just indicate if configured
        return jsonify({
            'success': True,
            'data': {
                'api_key_configured': api_key_valid,
                'api_secret_configured': api_secret_valid,
                'api_key_preview': config['api_key'][:8] + '...' if api_key_valid else 'Not configured',
                'is_connected': trading_service.is_connected
            }
        })
    except Exception as e:
        print(f"Error getting Binance env config: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading/settings', methods=['GET'])
def get_trading_settings():
    """Get trading settings"""
    try:
        status = trading_service.get_trading_status()
        return jsonify({'success': True, 'data': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading/settings', methods=['POST'])
def update_trading_settings():
    """Update trading settings"""
    try:
        data = request.get_json()
        success = trading_service.update_trading_settings(data)
        
        if success:
            return jsonify({'success': True, 'message': 'Trading settings updated'})
        else:
            return jsonify({'success': False, 'error': 'Failed to update settings'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading/connect', methods=['POST'])
def connect_trading():
    """Connect to Binance API for trading"""
    try:
        data = request.get_json()
        api_key = data.get('api_key')
        api_secret = data.get('api_secret')
        
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'API key and secret required'}), 400
        
        # Validate API key format
        if len(api_key) != 64:
            return jsonify({'success': False, 'error': 'Invalid API key format. Should be 64 characters long.'}), 400
        
        if len(api_secret) != 64:
            return jsonify({'success': False, 'error': 'Invalid API secret format. Should be 64 characters long.'}), 400
        
        # Update trading service credentials
        trading_service.api_key = api_key
        trading_service.api_secret = api_secret
        
        # Connect to Binance
        success = trading_service.connect_to_binance()
        
        if success:
            # Update settings to mark API as configured
            settings_update = {
                'api_settings': {
                    'api_key_configured': True,
                    'api_secret_configured': True
                }
            }
            trading_service.update_trading_settings(settings_update)
            
            return jsonify({'success': True, 'message': 'Connected to Binance successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to connect to Binance'})
            
    except Exception as e:
        print(f"Error in connect_trading endpoint: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading/test', methods=['POST'])
def test_trading_connection():
    """Test Binance API connection"""
    try:
        success, message = trading_service.test_connection()
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading/positions')
def get_trading_positions():
    """Get active trading positions"""
    try:
        positions = trading_service.get_active_positions()
        return jsonify({'success': True, 'data': positions})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading/close-position', methods=['POST'])
def close_trading_position():
    """Close trading position"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        reason = data.get('reason', 'Manual close')
        
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        
        success, message = trading_service.close_position(symbol, reason)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading/execute-manual', methods=['POST'])
def execute_manual_trade():
    """Execute manual trade from Entry button"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        signal_type = data.get('signal_type')
        entry_price = data.get('entry_price')
        
        if not all([symbol, signal_type, entry_price]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        
        success, message = trading_service.execute_manual_trade(symbol, signal_type, float(entry_price))
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading/execute-auto', methods=['POST'])
def execute_auto_trade():
    """Execute auto trade"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        signal_type = data.get('signal_type')
        entry_price = data.get('entry_price')
        signal_data = data.get('signal_data', {})
        
        if not all([symbol, signal_type, entry_price]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        
        success, message = trading_service.execute_auto_trade(symbol, signal_type, float(entry_price), signal_data)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/symbols/count')
def get_symbols_count():
    """Get total count of available symbols"""
    try:
        symbols = binance_service.get_futures_symbols()
        return jsonify({
            'success': True, 
            'data': {
                'total_symbols': len(symbols),
                'symbol_names': [s['symbol'] for s in symbols]
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)