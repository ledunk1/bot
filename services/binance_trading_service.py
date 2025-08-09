import json
import os
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
import threading
import time

class BinanceTradingService:
    """Service for live trading with Binance API"""
    
    def __init__(self, api_key=None, api_secret=None):
        # Load from .env first, then use provided values
        from config.env_config import EnvConfig
        env_config = EnvConfig()
        
        self.api_key = api_key or env_config.BINANCE_API_KEY
        self.api_secret = api_secret or env_config.BINANCE_API_SECRET
        self.client = None
        self.is_connected = False
        
        # Trading settings file
        self.settings_file = "trading_settings/trading_config.json"
        self.ensure_settings_dir()
        
        # Load trading settings
        self.trading_settings = self.load_trading_settings()
        
        # Active positions tracking
        self.active_positions = {}
        self.positions_lock = threading.Lock()
        
        # Initialize client if credentials provided
        if api_key and api_secret:
            self.connect_to_binance()
        elif self.api_key and self.api_secret:
            # Auto-connect if .env credentials are available
            print("🔑 Auto-connecting with .env credentials...")
            self.connect_to_binance()
    
    def ensure_settings_dir(self):
        """Ensure trading settings directory exists"""
        settings_dir = os.path.dirname(self.settings_file)
        if not os.path.exists(settings_dir):
            os.makedirs(settings_dir)
            print(f"Created trading settings directory: {settings_dir}")
    
    def get_default_trading_settings(self):
        """Get default trading settings"""
        return {
            "auto_trading": {
                "enabled": False,
                "max_symbols": 1,
                "leverage": 10,
                "margin_percent": 50,
                "min_winrate": 80,
                "min_pnl": 250,
                "max_drawdown": 60
            },
            "manual_trading": {
                "enabled": False,
                "leverage": 10,
                "margin_percent": 50
            },
            "risk_management": {
                "max_daily_loss": 10,  # Max 10% daily loss
                "max_positions": 3,    # Max 3 positions at once
                "stop_trading_on_loss": True
            },
            "api_settings": {
                "production_only": True,  # Always use production API
                "api_key_configured": False,
                "api_secret_configured": False
            }
        }
    
    def load_trading_settings(self):
        """Load trading settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                print(f"📁 Trading settings loaded from {self.settings_file}")
                return settings
            else:
                # Create default settings
                default_settings = self.get_default_trading_settings()
                self.save_trading_settings(default_settings)
                return default_settings
        except Exception as e:
            print(f"❌ Error loading trading settings: {str(e)}")
            return self.get_default_trading_settings()
    
    def save_trading_settings(self, settings):
        """Save trading settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            print(f"💾 Trading settings saved to {self.settings_file}")
            self.trading_settings = settings
            return True
        except Exception as e:
            print(f"❌ Error saving trading settings: {str(e)}")
            return False
    
    def connect_to_binance(self):
        """Connect to Binance API"""
        try:
            if not self.api_key or not self.api_secret:
                print("❌ API key and secret required for trading")
                return False
            
            print(f"🔑 Connecting with API Key: {self.api_key[:8]}...")
            print(f"🔐 API Secret configured: {bool(self.api_secret)}")
            
            # Always use production API
            print("🔗 Using Binance Production API (fapi.binance.com)")
            self.client = Client(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=False,
                requests_params={'timeout': 60}
            )
            
            # Test connection
            try:
                # First test with a simple API call
                server_time = self.client.get_server_time()
                print(f"✅ Server connection successful. Server time: {server_time}")
                
                # Then test futures account access
                account_info = self.client.futures_account()
                print(f"✅ Futures account access successful")
                
            except BinanceAPIException as api_error:
                print(f"❌ Binance API Error during connection test:")
                print(f"   Error Code: {api_error.code}")
                print(f"   Error Message: {api_error.message}")
                
                # Provide specific error guidance
                if api_error.code == -2015:
                    print("💡 Solution: Invalid API key, IP not whitelisted, or wrong permissions.")
                    print("   1. Verify you're using PRODUCTION API keys from https://www.binance.com")
                    print("   2. Check if your IP is whitelisted in API settings")
                    print("   3. Ensure API key has 'Enable Reading' and 'Enable Futures' permissions")
                    print("   4. Go to Binance.com > API Management > Edit API > IP Access Management")
                    print("   5. Add your current IP: 104.28.245.128 to the whitelist")
                    print("   6. Make sure 'Restrict access to trusted IPs only' is enabled")
                elif api_error.code == -1021:
                    print("💡 Solution: Timestamp issue. Check your system time.")
                elif api_error.code == -2014:
                    print("💡 Solution: API key format invalid.")
                elif "IP" in str(api_error.message):
                    print("💡 Solution: IP not whitelisted. Add your IP (104.28.245.128) to Binance API settings.")
                    print("   1. Go to https://www.binance.com/en/my/settings/api-management")
                    print("   2. Click 'Edit' on your API key")
                    print("   3. Go to 'IP Access Management'")
                    print("   4. Add IP: 104.28.245.128")
                    print("   5. Save changes and try again")
                elif "permission" in str(api_error.message).lower():
                    print("💡 Solution: Enable 'Enable Futures' permission in your API key settings.")
                    print("   1. Go to https://www.binance.com/en/my/settings/api-management")
                    print("   2. Click 'Edit' on your API key")
                    print("   3. Enable 'Enable Reading' checkbox")
                    print("   4. Enable 'Enable Futures' checkbox")
                    print("   5. Save changes")
                
                self.is_connected = False
                return False
                
            self.is_connected = True
            
            balance = float(account_info['totalWalletBalance'])
            print(f"✅ Binance connection successful. Balance: ${balance:.2f}")
            
            return True
            
        except BinanceAPIException as e:
            print(f"❌ Binance API Error:")
            print(f"   Code: {e.code}")
            print(f"   Message: {e.message}")
            
            # Enhanced error handling with solutions
            if e.code == -2015:
                print("💡 Fix: API key invalid, IP not whitelisted, or insufficient permissions")
                print("   Current IP that needs whitelisting: 104.28.245.128")
            elif e.code == -1021:
                print("💡 Fix: System time sync issue - sync your system clock")
            elif e.code == -2014:
                print("💡 Fix: API key format is invalid")
            elif "IP" in str(e.message):
                print("💡 Fix: Your IP address (104.28.245.128) is not whitelisted")
                print("   1. Go to Binance API Management")
                print("   2. Edit your API key")
                print("   3. Add IP address: 104.28.245.128 to whitelist")
                print("   4. Enable 'Restrict access to trusted IPs only'")
            elif "permission" in str(e.message).lower():
                print("💡 Fix: API key permissions insufficient")
                print("   1. Go to Binance API Management")
                print("   2. Edit your API key")
                print("   3. Enable 'Enable Futures' permission")
                print("   4. Enable 'Enable Reading' permission")
            
            self.is_connected = False
            return False
        except Exception as e:
            print(f"❌ Connection error: {str(e)}")
            self.is_connected = False
            return False
    
    def test_connection(self):
        """Test Binance API connection"""
        if not self.client:
            return False, "Client not initialized. Please connect first."
        
        try:
            # Test basic connection first
            print("🔍 Testing basic API connection...")
            server_time = self.client.get_server_time()
            
            # Test futures access
            print("🔍 Testing futures account access...")
            account_info = self.client.futures_account()
            balance = float(account_info['totalWalletBalance'])
            
            # Test exchange info access
            print("🔍 Testing exchange info access...")
            exchange_info = self.client.futures_exchange_info()
            
            success_msg = f"✅ All tests passed! Balance: ${balance:.2f}"
            print(success_msg)
            return True, success_msg
            
        except BinanceAPIException as e:
            error_msg = f"API Error {e.code}: {e.message}"
            print(f"❌ {error_msg}")
            
            # Provide specific solutions
            solutions = []
            if e.code == -2015:
                solutions.append("Check API key validity")
            elif e.code == -1021:
                solutions.append("Sync system time")
            elif "IP" in str(e.message):
                solutions.append("Whitelist your IP address")
            elif "permission" in str(e.message).lower():
                solutions.append("Enable Futures permission in API settings")
            
            if solutions:
                error_msg += f" | Solutions: {', '.join(solutions)}"
            
            return False, error_msg
        except Exception as e:
            error_msg = f"Connection error: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
    
    def get_account_balance(self):
        """Get account balance"""
        try:
            if not self.is_connected:
                return 0
            
            account_info = self.client.futures_account()
            return float(account_info['totalWalletBalance'])
        except Exception as e:
            print(f"Error getting balance: {str(e)}")
            return 0
    
    def check_auto_trading_criteria(self, symbol, signal_data):
        """Check if signal meets auto trading criteria"""
        try:
            if not self.trading_settings['auto_trading']['enabled']:
                return False, "Auto trading disabled"
            
            # Enhanced position check - allow opposite signals to close existing positions
            if symbol in self.active_positions and self.active_positions[symbol]['is_active']:
                existing_position = self.active_positions[symbol]
                existing_side = existing_position['side']
                new_signal_side = 'BUY' if signal_data.get('signal_value', 1) == 1 else 'SELL'
                
                # If opposite signal, allow it to close existing position
                if ((existing_side == 'BUY' and new_signal_side == 'SELL') or 
                    (existing_side == 'SELL' and new_signal_side == 'BUY')):
                    print(f"🔄 Opposite signal detected for {symbol}: {existing_side} → {new_signal_side}")
                    return True, f"Opposite signal - will close existing {existing_side} position"
                else:
                    # Same direction signal - ignore
                    return False, f"Same direction signal ignored - already have {existing_side} position"
            
            # Check if we already have max positions
            active_count = len([p for p in self.active_positions.values() if p['is_active']])
            if active_count >= self.trading_settings['auto_trading']['max_symbols']:
                # Allow if this is an opposite signal that will close existing position
                if symbol in self.active_positions and self.active_positions[symbol]['is_active']:
                    existing_side = self.active_positions[symbol]['side']
                    new_signal_side = 'BUY' if signal_data.get('signal_value', 1) == 1 else 'SELL'
                    if existing_side != new_signal_side:
                        return True, f"Opposite signal allowed to close existing position"
                
                return False, f"Max positions reached ({active_count}/{self.trading_settings['auto_trading']['max_symbols']})"
            
            # Get coin settings to check historical performance
            from services.coin_settings_manager import CoinSettingsManager
            settings_manager = CoinSettingsManager()
            coin_settings = settings_manager.load_coin_settings(symbol)
            
            # Check criteria
            criteria = self.trading_settings['auto_trading']
            
            if coin_settings.get('optimization_score', 0) <= 0:
                return False, "No optimization data available"
            
            backtest_stats = coin_settings.get('backtest_stats', {})
            
            # Check win rate
            win_rate = backtest_stats.get('win_rate', 0)
            if win_rate < criteria['min_winrate']:
                return False, f"Win rate too low: {win_rate:.1f}% < {criteria['min_winrate']}%"
            
            # Check total return (PnL)
            total_return = backtest_stats.get('total_return', 0)
            if total_return < criteria['min_pnl']:
                return False, f"Total return too low: {total_return:.1f}% < {criteria['min_pnl']}%"
            
            # Check max drawdown
            max_drawdown = backtest_stats.get('max_drawdown', 100)
            if max_drawdown > criteria['max_drawdown']:
                return False, f"Max drawdown too high: {max_drawdown:.1f}% > {criteria['max_drawdown']}%"
            
            return True, "All criteria met"
            
        except Exception as e:
            print(f"Error checking auto trading criteria: {str(e)}")
            return False, str(e)
    
    def execute_auto_trade(self, symbol, signal_type, entry_price, signal_data):
        """Execute automatic trade based on criteria"""
        try:
            # Enhanced auto trading logic with opposite signal handling
            print(f"🤖 Processing auto trade: {symbol} {signal_type} at ${entry_price}")
            
            # Check if we have existing position for this symbol
            if symbol in self.active_positions and self.active_positions[symbol]['is_active']:
                existing_position = self.active_positions[symbol]
                existing_side = existing_position['side']
                new_signal_side = signal_type.upper()
                
                # If opposite signal, close existing position first
                if ((existing_side == 'BUY' and new_signal_side == 'SELL') or 
                    (existing_side == 'SELL' and new_signal_side == 'BUY')):
                    
                    print(f"🔄 Closing existing {existing_side} position due to opposite {new_signal_side} signal")
                    close_success, close_message = self.close_position(symbol, f"Opposite signal: {new_signal_side}")
                    
                    if close_success:
                        print(f"✅ Existing position closed: {close_message}")
                        # Continue to open new position
                    else:
                        print(f"❌ Failed to close existing position: {close_message}")
                        return False, f"Failed to close existing position: {close_message}"
                else:
                    # Same direction signal - ignore
                    return False, f"Same direction signal ignored - already have {existing_side} position"
            
            # Check criteria first
            can_trade, reason = self.check_auto_trading_criteria(symbol, signal_data)
            if not can_trade:
                # Special handling for opposite signals
                if "opposite signal" in reason.lower():
                    print(f"🔄 Auto trade proceeding for opposite signal: {symbol}")
                else:
                    print(f"⏭️ Auto trade skipped for {symbol}: {reason}")
                    return False, reason
            
            if not self.is_connected:
                return False, "Not connected to Binance"
            
            # Use same logic as manual trade but with auto trading settings
            success, result = self._execute_trade_order(symbol, signal_type, entry_price, 'auto', signal_data)
            
            if success:
                print(f"🤖 Auto trade executed successfully: {symbol} {signal_type}")
                # Add auto trading specific info to result
                enhanced_result = f"{result}\n\n🤖 **AUTO TRADING ACTIVE**\n• Position will be monitored for opposite signals\n• Automatic close on reverse signal\n• TP/SL managed by strategy"
                return True, enhanced_result
            else:
                return False, result
            
        except BinanceAPIException as e:
            print(f"❌ Binance API Error in auto trade: {e.message}")
            
            # Enhanced error handling for auto trade
            error_msg = f"API Error {e.code}: {e.message}"
            if e.code == -1111:
                error_msg += "\n💡 Solution: Quantity precision error"
            elif e.code == -2019:
                error_msg += "\n💡 Solution: Insufficient margin balance"
            elif e.code == -4131:
                error_msg += "\n💡 Solution: Order size below minimum"
            
            return False, f"API Error: {e.message}"
        except Exception as e:
            print(f"❌ Error executing auto trade: {str(e)}")
            return False, str(e)
    
    def _execute_trade_order(self, symbol, signal_type, entry_price, trade_type='manual', signal_data=None, user_id=None):
        """Common trade execution logic for both manual and auto trading"""
        try:
            # Get symbol info for precision rules
            exchange_info = self.client.futures_exchange_info()
            symbol_info = None
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    symbol_info = s
                    break
            
            if not symbol_info:
                return False, f"Symbol {symbol} not found in exchange info"
            
            # Get precision rules
            quantity_precision = int(symbol_info['quantityPrecision'])
            price_precision = int(symbol_info['pricePrecision'])
            
            # Get minimum quantity from filters
            min_qty = 0.001  # Default minimum
            step_size = 0.001  # Default step size
            
            for filter_info in symbol_info['filters']:
                if filter_info['filterType'] == 'LOT_SIZE':
                    min_qty = float(filter_info['minQty'])
                    step_size = float(filter_info['stepSize'])
                    break
            
            print(f"📊 {symbol} precision rules: qty_precision={quantity_precision}, min_qty={min_qty}, step_size={step_size}")
            
            # Calculate position size based on trade type
            balance = self.get_account_balance()
            if balance <= 0:
                return False, "Insufficient balance"
            
            if trade_type == 'auto':
                leverage = self.trading_settings['auto_trading']['leverage']
                margin_percent = self.trading_settings['auto_trading']['margin_percent']
            else:  # manual
                leverage = self.trading_settings['manual_trading']['leverage']
                margin_percent = self.trading_settings['manual_trading']['margin_percent']
            
            margin_amount = balance * (margin_percent / 100)
            position_value = margin_amount * leverage
            quantity = position_value / entry_price
            
            print(f"💰 Calculated quantity before precision: {quantity:.8f}")
            
            # Apply precision rules
            # Round to step size
            quantity = round(quantity / step_size) * step_size
            
            # Apply quantity precision
            quantity = round(quantity, quantity_precision)
            
            print(f"💰 Quantity after precision adjustment: {quantity:.8f}")
            
            # Validate minimum order size
            if quantity < min_qty:
                return False, f"Order size too small: {quantity:.{quantity_precision}f} < {min_qty}. Increase margin or balance."
            
            # Additional validation for very small quantities
            if quantity <= 0:
                return False, f"Invalid quantity: {quantity:.{quantity_precision}f}. Check balance and margin settings."
            
            # Set leverage for symbol
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            
            # Place market order
            side = 'BUY' if signal_type.upper() == 'BUY' else 'SELL'
            
            print(f"🔄 Placing {trade_type} order: {side} {quantity:.{quantity_precision}f} {symbol}")
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            
            # Get actual fill price
            actual_price = float(order.get('avgPrice', entry_price))
            
            # Store position info
            with self.positions_lock:
                self.active_positions[symbol] = {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'entry_price': actual_price,
                    'leverage': leverage,
                    'margin_used': margin_amount,
                    'order_id': order['orderId'],
                    'is_active': True,
                    'entry_time': datetime.now(),
                    'user_id': user_id,
                    'trade_type': trade_type,
                    'signal_data': signal_data,
                    'pnl': 0  # Initialize PnL
                }
            
            trade_emoji = "🤖" if trade_type == 'auto' else "💰"
            print(f"{trade_emoji} {trade_type.title()} trade executed: {side} {quantity:.{quantity_precision}f} {symbol} at ${actual_price:.4f}")
            return True, f"{trade_emoji} {side} {quantity:.{quantity_precision}f} {symbol} at ${actual_price:.4f}\n💰 Margin: ${margin_amount:.2f} | Leverage: {leverage}x"
            
        except Exception as e:
            print(f"❌ Error in trade execution: {str(e)}")
            raise e
    
    def execute_manual_trade(self, symbol, signal_type, entry_price, user_id=None):
        """Execute manual trade from Telegram entry button"""
        try:
            if not self.is_connected:
                return False, "Not connected to Binance"
            
            if not self.trading_settings['manual_trading']['enabled']:
                return False, "Manual trading disabled"
            
            # Check if we already have a position for this symbol
            if symbol in self.active_positions and self.active_positions[symbol]['is_active']:
                return False, f"Already have active position for {symbol}"
            
            # Use common trade execution logic
            return self._execute_trade_order(symbol, signal_type, entry_price, 'manual', None, user_id)
            
        except BinanceAPIException as e:
            print(f"❌ Binance API Error in manual trade: {e.message}")
            
            # Provide specific error solutions
            error_msg = f"API Error {e.code}: {e.message}"
            if e.code == -2019:
                error_msg += "\n💡 Solution: Insufficient margin balance"
            elif e.code == -1111:
                error_msg += "\n💡 Solution: Quantity precision error - order size doesn't match symbol rules"
            elif e.code == -4131:
                error_msg += "\n💡 Solution: Order size below minimum"
            elif e.code == -1013:
                error_msg += "\n💡 Solution: Invalid quantity precision"
            
            return False, error_msg
        except Exception as e:
            print(f"❌ Error executing manual trade: {str(e)}")
            return False, str(e)
    
    def close_position(self, symbol, reason="Manual close"):
        """Close position for symbol"""
        try:
            if symbol not in self.active_positions:
                return False, "No active position found"
            
            position = self.active_positions[symbol]
            if not position['is_active']:
                return False, "Position already closed"
            
            print(f"🔄 Closing position for {symbol}: {position['side']} - Reason: {reason}")
            
            # Get symbol precision for closing
            exchange_info = self.client.futures_exchange_info()
            quantity_precision = 6  # Default
            
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    quantity_precision = int(s['quantityPrecision'])
                    break
            
            # Round quantity to proper precision
            close_quantity = round(position['quantity'], quantity_precision)
            
            # Close position with opposite side
            close_side = 'SELL' if position['side'] == 'BUY' else 'BUY'
            
            print(f"📊 Executing close order: {close_side} {close_quantity:.{quantity_precision}f} {symbol}")
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type='MARKET',
                quantity=close_quantity
            )
            
            # Calculate PnL for the closed position
            try:
                fill_price = float(order.get('avgPrice', 0))
                if fill_price > 0:
                    entry_price = position['entry_price']
                    if position['side'] == 'BUY':
                        pnl_percent = ((fill_price - entry_price) / entry_price) * 100
                    else:  # SELL
                        pnl_percent = ((entry_price - fill_price) / entry_price) * 100
                    
                    pnl_amount = pnl_percent * position['margin_used'] * position['leverage'] / 100
                    position['final_pnl'] = pnl_amount
                    position['final_pnl_percent'] = pnl_percent
                    position['close_price'] = fill_price
                    
                    print(f"💰 Position PnL: {pnl_percent:+.2f}% (${pnl_amount:+.2f})")
            except Exception as pnl_error:
                print(f"⚠️ Error calculating PnL: {str(pnl_error)}")
            
            # Update position
            with self.positions_lock:
                self.active_positions[symbol]['is_active'] = False
                self.active_positions[symbol]['close_time'] = datetime.now()
                self.active_positions[symbol]['close_reason'] = reason
                self.active_positions[symbol]['close_order_id'] = order['orderId']
            
            print(f"✅ Position closed: {symbol} - {reason}")
            
            # Enhanced close message with PnL info
            close_message = f"Position closed: {symbol}"
            if 'final_pnl_percent' in position:
                pnl_emoji = "📈" if position['final_pnl_percent'] >= 0 else "📉"
                close_message += f" {pnl_emoji} PnL: {position['final_pnl_percent']:+.2f}%"
            
            return True, close_message
            
        except BinanceAPIException as e:
            print(f"❌ Binance API Error closing position: {e.message}")
            return False, f"API Error: {e.message}"
        except Exception as e:
            print(f"❌ Error closing position: {str(e)}")
            return False, str(e)
    
    def get_active_positions(self):
        """Get all active positions"""
        try:
            with self.positions_lock:
                active_positions = {}
                for symbol, position in self.active_positions.items():
                    if position['is_active']:
                        # Calculate current PnL
                        position_copy = position.copy()
                        position_copy['pnl'] = self.get_position_pnl(symbol)
                        active_positions[symbol] = position_copy
                
                return active_positions
        except Exception as e:
            print(f"Error getting active positions: {str(e)}")
            return {}
    
    def get_position_pnl(self, symbol):
        """Get current PnL for position"""
        try:
            if symbol not in self.active_positions:
                return 0
            
            position = self.active_positions[symbol]
            if not position['is_active']:
                return 0
            
            # Get current price
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            entry_price = position['entry_price']
            quantity = position['quantity']
            side = position['side']
            
            # Calculate PnL
            if side == 'BUY':
                pnl = (current_price - entry_price) * quantity
            else:  # SELL
                pnl = (entry_price - current_price) * quantity
            
            return pnl
            
        except Exception as e:
            print(f"Error calculating PnL for {symbol}: {str(e)}")
            return 0
    
    def update_trading_settings(self, new_settings):
        """Update trading settings"""
        try:
            # Merge with existing settings
            updated_settings = self.trading_settings.copy()
            
            # Update auto trading settings
            if 'auto_trading' in new_settings:
                updated_settings['auto_trading'].update(new_settings['auto_trading'])
            
            # Update manual trading settings
            if 'manual_trading' in new_settings:
                updated_settings['manual_trading'].update(new_settings['manual_trading'])
            
            # Update risk management settings
            if 'risk_management' in new_settings:
                updated_settings['risk_management'].update(new_settings['risk_management'])
            
            # Update API settings
            if 'api_settings' in new_settings:
                updated_settings['api_settings'].update(new_settings['api_settings'])
            
            # Save updated settings
            return self.save_trading_settings(updated_settings)
            
        except Exception as e:
            print(f"Error updating trading settings: {str(e)}")
            return False
    
    def get_trading_status(self):
        """Get trading service status"""
        active_positions = self.get_active_positions()
        
        return {
            'is_connected': self.is_connected,
            'balance': self.get_account_balance() if self.is_connected else 0,
            'active_positions_count': len(active_positions),
            'active_positions': active_positions,
            'auto_trading_enabled': self.trading_settings['auto_trading']['enabled'],
            'manual_trading_enabled': self.trading_settings['manual_trading']['enabled'],
            'testnet': self.trading_settings.get('api_settings', {}).get('testnet', False),
            'settings': self.trading_settings
        }