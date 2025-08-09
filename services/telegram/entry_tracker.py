import threading
import time
from datetime import datetime, timedelta

class TelegramEntryTracker:
    """Handle entry tracking and TP/SL monitoring"""
    
    def __init__(self, base_service, trading_service=None):
        self.base_service = base_service
        self.trading_service = trading_service
        
        # Entry tracking system
        self.active_entries = {}  # {symbol: {entry_data, tp_levels_hit, is_active}}
        self.tracking_thread = None
        self.is_tracking = False
        
        # Start tracking thread
        self._start_tracking_thread()
    
    def handle_entry_callback(self, symbol, signal_type, entry_price):
        """Handle when user clicks Entry button"""
        try:
            print(f"🎯 Processing entry callback: {symbol} {signal_type} at ${entry_price}")
            
            entry_price = float(entry_price)
            direction = 1 if signal_type.upper() == "BUY" else -1
            
            # Check if trading is enabled and execute trade
            trade_executed = False
            trade_message = ""
            
            if (self.trading_service and 
                self.trading_service.is_connected and 
                self.trading_service.trading_settings['manual_trading']['enabled']):
                
                # Execute manual trade
                success, result = self.trading_service.execute_manual_trade(
                    symbol, signal_type, entry_price
                )
                
                if success:
                    trade_executed = True
                    trade_message = f"\n\n💰 **LIVE TRADE EXECUTED**\n{result}"
                else:
                    trade_message = f"\n\n⚠️ **Trade Failed:** {result}"
            
            # Calculate TP/SL levels
            from services.telegram.message_formatter import TelegramMessageFormatter
            tp_levels, sl_level = TelegramMessageFormatter.calculate_tp_sl_levels(entry_price, direction)
            
            # Store entry data for tracking
            self.active_entries[symbol] = {
                'symbol': symbol,
                'signal_type': signal_type,
                'entry_price': entry_price,
                'direction': direction,
                'tp_levels': tp_levels,
                'sl_level': sl_level,
                'tp_levels_hit': [],
                'is_active': True,
                'entry_time': datetime.now(),
                'last_price': entry_price
            }
            
            # Send confirmation message
            confirmation_msg = f"""
✅ **ENTRY CONFIRMED - {symbol}**

🎯 **Position:** {signal_type}
💰 **Entry Price:** ${entry_price:.4f}
⏰ **Entry Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{trade_message}

📊 **TP/SL Tracking ACTIVATED**
• You will receive notifications when TP/SL levels are hit
• Click "Done" button when you want to stop tracking

🎯 **Take Profit Levels:**
"""
            
            # Add TP levels to message
            for tp in tp_levels[:5]:
                confirmation_msg += f"TP{tp['level']}: ${tp['price']:.4f} (+{tp['percent']:.2f}%)\n"
            
            confirmation_msg += f"\n🛑 **Stop Loss:** ${sl_level:.4f} (-1.50%)"
            
            # Create Done button
            import json
            done_keyboard = {
                "inline_keyboard": [[
                    {
                        "text": f"✅ DONE - {symbol}",
                        "callback_data": f"done_{symbol}"
                    }
                ]]
            }
            
            self.base_service._send_message(confirmation_msg.strip(), {
                'reply_markup': json.dumps(done_keyboard)
            })
            
            print(f"✅ Entry tracking started for {symbol} at ${entry_price:.4f}")
            return True
            
        except Exception as e:
            print(f"Error handling entry callback: {str(e)}")
            # Send error message to user
            try:
                error_msg = f"❌ **Error starting tracking for {symbol}**\n\nPlease try again or contact support."
                self.base_service._send_message(error_msg)
            except:
                pass
            return False
    
    def handle_live_trade_callback(self, symbol, signal_type, entry_price):
        """Handle live trade button callback"""
        try:
            if not self.trading_service or not self.trading_service.is_connected:
                self.base_service._send_message(f"❌ **Trading not available for {symbol}**\n\nBinance API not connected.")
                return False
            
            if not self.trading_service.trading_settings['manual_trading']['enabled']:
                self.base_service._send_message(f"❌ **Manual trading disabled for {symbol}**\n\nEnable manual trading in settings.")
                return False
            
            # Execute manual trade
            success, result = self.trading_service.execute_manual_trade(
                symbol, signal_type, float(entry_price)
            )
            
            if success:
                message = f"""
✅ **LIVE TRADE EXECUTED - {symbol}**

💰 **Trade Details:**
{result}

⏰ **Execution Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 **Next Steps:**
• Monitor position in your Binance account
• Set manual TP/SL levels if needed
• Track performance
                """
                self.base_service._send_message(message.strip())
                return True
            else:
                error_message = f"""
❌ **TRADE FAILED - {symbol}**

**Error:** {result}

**Possible Solutions:**
• Check your account balance
• Verify API permissions
• Check symbol trading status
• Review margin requirements
                """
                self.base_service._send_message(error_message.strip())
                return False
                
        except Exception as e:
            print(f"Error handling live trade callback: {str(e)}")
            self.base_service._send_message(f"❌ **Error executing trade for {symbol}**\n\n{str(e)}")
            return False
    
    def handle_auto_trade_callback(self, symbol, signal_type, entry_price):
        """Handle auto trade button callback"""
        try:
            print(f"🤖 Processing auto trade callback: {symbol} {signal_type} at ${entry_price}")
            
            if not self.trading_service or not self.trading_service.is_connected:
                self.base_service._send_message(f"❌ **Auto trading not available for {symbol}**\n\nBinance API not connected.")
                return False
            
            if not self.trading_service.trading_settings['auto_trading']['enabled']:
                self.base_service._send_message(f"❌ **Auto trading disabled for {symbol}**\n\nEnable auto trading in settings.")
                return False
            
            # Enhanced logic for opposite signals
            has_existing_position = (symbol in self.trading_service.active_positions and 
                                   self.trading_service.active_positions[symbol]['is_active'])
            
            if has_existing_position:
                existing_position = self.trading_service.active_positions[symbol]
                existing_side = existing_position['side']
                new_signal_side = signal_type.upper()
                
                # Check if this is an opposite signal
                if ((existing_side == 'BUY' and new_signal_side == 'SELL') or 
                    (existing_side == 'SELL' and new_signal_side == 'BUY')):
                    
                    # This is an opposite signal - close existing and open new
                    print(f"🔄 Processing opposite signal: Close {existing_side} → Open {new_signal_side}")
                    
                    # Close existing position first
                    close_success, close_message = self.trading_service.close_position(
                        symbol, f"Opposite signal: {new_signal_side}"
                    )
                    
                    if not close_success:
                        error_message = f"""
❌ **FAILED TO CLOSE EXISTING POSITION - {symbol}**

**Error:** {close_message}

**Current Position:** {existing_side}
**New Signal:** {new_signal_side}

**Action Required:**
• Manually close existing position
• Then retry auto trade
                        """
                        self.base_service._send_message(error_message.strip())
                        return False
                    
                    # Add delay to ensure position is closed
                    import time
                    time.sleep(1)
                    
                    print(f"✅ Existing {existing_side} position closed, proceeding with {new_signal_side}")
                else:
                    # Same direction signal - inform user
                    self.base_service._send_message(f"⏭️ **Same direction signal ignored for {symbol}**\n\nAlready have {existing_side} position active.")
                    return False
            
            # This would typically be handled automatically, but user can manually trigger
            signal_data = {
                'symbol': symbol,
                'signal': signal_type,
                'entry_price': float(entry_price)
            }
            
            success, result = self.trading_service.execute_auto_trade(
                symbol, signal_type, float(entry_price), signal_data
            )
            
            if success:
                action_text = "🔄 **POSITION SWITCHED**" if has_existing_position else "🤖 **AUTO TRADE EXECUTED**"
                message = f"""
{action_text} - {symbol}**

💰 **Trade Details:**
{result}

⏰ **Execution Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{f"🔄 **Action:** Closed previous position and opened new {signal_type} position" if has_existing_position else ""}

📊 **Auto Trading Active:**
• Position will be managed automatically
• TP/SL levels set according to strategy
• Monitoring for opposite signals
• Monitor in positions panel
                """
                self.base_service._send_message(message.strip())
                return True
            else:
                error_message = f"""
❌ **AUTO TRADE FAILED - {symbol}**

**Reason:** {result}

**Auto Trading Criteria:**
• Check if symbol meets win rate requirements
• Verify PnL and drawdown criteria
• Ensure max positions limit not reached
• Verify opposite signal handling
                """
                self.base_service._send_message(error_message.strip())
                return False
                
        except Exception as e:
            print(f"Error handling auto trade callback: {str(e)}")
            self.base_service._send_message(f"❌ **Error executing auto trade for {symbol}**\n\n{str(e)}")
            return False
    
    def handle_done_callback(self, symbol):
        """Handle when user clicks Done button"""
        try:
            if symbol in self.active_entries:
                entry_data = self.active_entries[symbol]
                
                # Mark as inactive
                self.active_entries[symbol]['is_active'] = False
                
                # Send completion message
                completion_msg = f"""
✅ **TRACKING COMPLETED - {symbol}**

📊 **Final Summary:**
• Entry: ${entry_data['entry_price']:.4f}
• Signal: {entry_data['signal_type']}
• TPs Hit: {len(entry_data['tp_levels_hit'])}
• Duration: {self._get_duration_text(entry_data['entry_time'])}

🔕 **Notifications STOPPED for {symbol}**
Thank you for using our signal service!
                """
                
                self.base_service._send_message(completion_msg.strip())
                
                # Remove from active entries after a delay
                threading.Timer(300, lambda: self.active_entries.pop(symbol, None)).start()
                
                print(f"✅ Entry tracking completed for {symbol}")
                return True
            else:
                self.base_service._send_message(f"❌ No active tracking found for {symbol}")
                return False
                
        except Exception as e:
            print(f"Error handling done callback: {str(e)}")
            return False
    
    def _start_tracking_thread(self):
        """Start background thread to track TP/SL levels"""
        if not self.is_tracking:
            self.is_tracking = True
            self.tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
            self.tracking_thread.start()
            print("📊 TP/SL tracking thread started")
    
    def _tracking_loop(self):
        """Background loop to check TP/SL levels"""
        from services.binance_service import BinanceService
        binance_service = BinanceService()
        
        while self.is_tracking:
            try:
                if not self.active_entries:
                    time.sleep(30)  # Check every 30 seconds if no active entries
                    continue
                
                # Check each active entry
                for symbol, entry_data in list(self.active_entries.items()):
                    if not entry_data['is_active']:
                        continue
                    
                    try:
                        # Get current price
                        current_price = self._get_current_price(binance_service, symbol)
                        if current_price is None:
                            continue
                        
                        entry_data['last_price'] = current_price
                        
                        # Check TP/SL levels
                        self._check_tp_sl_levels(symbol, entry_data, current_price)
                        
                    except Exception as e:
                        print(f"Error checking {symbol}: {str(e)}")
                        continue
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                print(f"Error in tracking loop: {str(e)}")
                time.sleep(30)
    
    def _get_current_price(self, binance_service, symbol):
        """Get current price for symbol"""
        try:
            # Use UTC time to avoid timezone issues
            from datetime import timezone
            end_date = datetime.now(timezone.utc).replace(tzinfo=None)
            start_date = end_date - timedelta(minutes=10)  # Increased to 10 minutes for better data availability
            
            df = binance_service.get_klines(
                symbol, '1m',
                start_date.strftime('%Y-%m-%d %H:%M:%S'),
                end_date.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            if not df.empty:
                return float(df.iloc[-1]['close'])
            
            # Fallback: try with longer time range if no data
            start_date = end_date - timedelta(hours=1)
            df = binance_service.get_klines(
                symbol, '5m',
                start_date.strftime('%Y-%m-%d %H:%M:%S'),
                end_date.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            if not df.empty:
                return float(df.iloc[-1]['close'])
            
            # Final fallback: try with even longer range
            start_date = end_date - timedelta(hours=24)
            df = binance_service.get_klines(
                symbol, '1h',
                start_date.strftime('%Y-%m-%d %H:%M:%S'),
                end_date.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            if not df.empty:
                return float(df.iloc[-1]['close'])
            
            return None
            
        except Exception as e:
            print(f"Error getting current price for {symbol}: {str(e)}")
            return None
    
    def _check_tp_sl_levels(self, symbol, entry_data, current_price):
        """Check if TP or SL levels are hit"""
        try:
            direction = entry_data['direction']
            tp_levels = entry_data['tp_levels']
            sl_level = entry_data['sl_level']
            tp_levels_hit = entry_data['tp_levels_hit']
            
            # Check Stop Loss first
            sl_hit = False
            if direction == 1:  # Long
                sl_hit = current_price <= sl_level
            else:  # Short
                sl_hit = current_price >= sl_level
            
            if sl_hit:
                self._send_tp_sl_notification(symbol, entry_data, current_price, "STOP LOSS", sl_level)
                entry_data['is_active'] = False
                return
            
            # Check Take Profit levels
            for tp in tp_levels:
                if tp['level'] in tp_levels_hit:
                    continue  # Already hit
                
                tp_hit = False
                if direction == 1:  # Long
                    tp_hit = current_price >= tp['price']
                else:  # Short
                    tp_hit = current_price <= tp['price']
                
                if tp_hit:
                    tp_levels_hit.append(tp['level'])
                    self._send_tp_sl_notification(symbol, entry_data, current_price, f"TP{tp['level']}", tp['price'])
                    
                    # If all TPs hit, mark as inactive
                    if len(tp_levels_hit) >= 5:  # First 5 TPs
                        entry_data['is_active'] = False
                        self.base_service._send_message(f"🎉 **ALL TPs HIT - {symbol}**\n\nCongratulations! All take profit levels reached.\nClick Done to stop tracking.")
                    
                    break  # Only process one TP at a time
            
        except Exception as e:
            print(f"Error checking TP/SL levels for {symbol}: {str(e)}")
    
    def _send_tp_sl_notification(self, symbol, entry_data, current_price, level_type, target_price):
        """Send TP/SL hit notification"""
        try:
            entry_price = entry_data['entry_price']
            signal_type = entry_data['signal_type']
            
            # Calculate PnL percentage
            if entry_data['direction'] == 1:  # Long
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
            else:  # Short
                pnl_percent = ((entry_price - current_price) / entry_price) * 100
            
            # Determine emoji and color
            if level_type == "STOP LOSS":
                emoji = "🛑❌"
                pnl_text = f"Loss: -{abs(pnl_percent):.2f}%"
            else:
                emoji = "🎯✅"
                pnl_text = f"Profit: +{pnl_percent:.2f}%"
            
            message = f"""
{emoji} **{level_type} HIT - {symbol}** {emoji}

📊 **Trade Update:**
• Signal: {signal_type}
• Entry: ${entry_price:.4f}
• Target: ${target_price:.4f}
• Current: ${current_price:.4f}
• {pnl_text}

⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🕐 **Duration:** {self._get_duration_text(entry_data['entry_time'])}

{f"🎯 **TPs Hit:** {len(entry_data['tp_levels_hit'])}/5" if level_type != "STOP LOSS" else ""}

💡 **Next Action:** {"Consider taking partial profits" if level_type.startswith("TP") else "Review your strategy"}
            """
            
            # Add Done button for easy completion
            import json
            done_keyboard = {
                "inline_keyboard": [[
                    {
                        "text": f"✅ DONE - {symbol}",
                        "callback_data": f"done_{symbol}"
                    }
                ]]
            }
            
            self.base_service._send_message(message.strip(), {
                'reply_markup': json.dumps(done_keyboard)
            })
            
            print(f"🎯 {level_type} notification sent for {symbol} at ${current_price:.4f}")
            
        except Exception as e:
            print(f"Error sending TP/SL notification: {str(e)}")
    
    def _get_duration_text(self, start_time):
        """Get human readable duration text"""
        try:
            duration = datetime.now() - start_time
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            
            if hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except:
            return "N/A"
    
    def get_active_entries_status(self):
        """Get status of all active entries"""
        active_count = sum(1 for entry in self.active_entries.values() if entry['is_active'])
        return {
            'total_entries': len(self.active_entries),
            'active_entries': active_count,
            'symbols': list(self.active_entries.keys())
        }