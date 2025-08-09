import requests
import json
import io
from datetime import datetime

class BaseTelegramService:
    """Base Telegram service with core functionality"""
    
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token or "YOUR_BOT_TOKEN"
        self.chat_id = chat_id or "YOUR_CHAT_ID"
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Validate and fix chat_id format
        self.chat_id = self._validate_chat_id(self.chat_id)
        
        # Configure bot for enhanced mode with callback support
        self._configure_enhanced_mode()
    
    def _validate_chat_id(self, chat_id):
        """Validate and fix chat_id format"""
        try:
            if not chat_id or chat_id in ["YOUR_CHAT_ID", ""]:
                print("⚠️ Warning: Chat ID not configured")
                return chat_id
            
            # Convert to string and remove any whitespace
            chat_id = str(chat_id).strip()
            
            # Don't modify chat_id - use exactly as provided in .env
            print(f"🔧 Using chat_id as provided: {chat_id}")
            
            return chat_id
            
        except Exception as e:
            print(f"Error validating chat_id: {str(e)}")
            return chat_id
    
    def _configure_enhanced_mode(self):
        """Configure bot for enhanced mode with callback support"""
        try:
            # Skip configuration if bot token or chat_id not properly set
            if (not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN" or
                not self.chat_id or self.chat_id == "YOUR_CHAT_ID"):
                print("⚠️ Skipping bot configuration - credentials not set")
                return
            
            # Delete webhook to enable getUpdates polling for callbacks
            url = f"{self.base_url}/deleteWebhook"
            response = requests.post(url)
            print(f"Webhook deleted: {response.json()}")
            
            # Keep commands empty but allow callbacks
            url = f"{self.base_url}/setMyCommands"
            data = {'commands': json.dumps([])}
            response = requests.post(url, data=data)
            print(f"Commands cleared: {response.json()}")
            
            print("✅ Bot configured for enhanced mode with callback support")
            
        except Exception as e:
            print(f"Warning: Could not configure enhanced mode: {str(e)}")
    
    def _configure_broadcast_mode(self):
        """Configure bot for broadcast mode"""
        try:
            # Skip configuration if bot token or chat_id not properly set
            if (not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN" or
                not self.chat_id or self.chat_id == "YOUR_CHAT_ID"):
                print("⚠️ Skipping broadcast mode configuration - credentials not set")
                return
            
            # Delete webhook to enable getUpdates polling for callbacks
            url = f"{self.base_url}/deleteWebhook"
            response = requests.post(url)
            print(f"Webhook deleted for broadcast mode: {response.json()}")
            
            # Clear commands for broadcast mode
            url = f"{self.base_url}/setMyCommands"
            data = {'commands': json.dumps([])}
            response = requests.post(url, data=data)
            print(f"Commands cleared for broadcast mode: {response.json()}")
            
            # Set bot description for broadcast mode
            url = f"{self.base_url}/setMyDescription"
            data = {
                'description': """🤖 Enhanced Crypto Trading Signal Bot - BROADCAST MODE ONLY

📢 This bot sends automated trading signals with interactive TP/SL tracking.
🚫 Bot does not respond to messages or commands.
📈 Click "Entry" button to start tracking TP/SL levels.
🎯 Get notifications when TP/SL levels are hit.
✅ Click "Done" to stop tracking anytime.
⚠️ For educational purposes only - DYOR before trading."""
            }
            
            response = requests.post(url, data=data)
            if response.json().get('ok'):
                print("✅ Bot description set for broadcast mode")
            
            print("✅ Bot configured for broadcast mode successfully")
            
        except Exception as e:
            print(f"Warning: Could not configure broadcast mode: {str(e)}")
    
    def _process_callback_updates(self):
        """Process callback queries from Telegram"""
        try:
            # Skip if not properly configured
            if (not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN" or
                not self.chat_id or self.chat_id == "YOUR_CHAT_ID"):
                return
            
            url = f"{self.base_url}/getUpdates"
            params = {'timeout': 1, 'allowed_updates': ['callback_query']}
            
            response = requests.get(url, params=params, timeout=2)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    for update in data['result']:
                        if 'callback_query' in update:
                            self._handle_callback_query(update['callback_query'])
                    
                    # Acknowledge updates
                    if data['result']:
                        last_update_id = data['result'][-1]['update_id']
                        requests.get(f"{self.base_url}/getUpdates", 
                                   params={'offset': last_update_id + 1})
            
        except Exception as e:
            # Silent fail for callback processing
            pass
    
    def _handle_callback_query(self, callback_query):
        """Handle callback query from inline buttons"""
        try:
            callback_data = callback_query.get('data', '')
            query_id = callback_query.get('id')
            
            # Answer callback query to remove loading state
            answer_url = f"{self.base_url}/answerCallbackQuery"
            requests.post(answer_url, data={'callback_query_id': query_id})
            
            # Process callback data
            if callback_data.startswith('entry_'):
                parts = callback_data.split('_')
                if len(parts) >= 4:
                    symbol = parts[1]
                    signal_type = parts[2]
                    entry_price = parts[3]
                    
                    # Import here to avoid circular import
                    from services.telegram_service import TelegramService
                    if hasattr(self, 'handle_entry_callback'):
                        self.handle_entry_callback(symbol, signal_type, entry_price)
                    
            elif callback_data.startswith('done_'):
                symbol = callback_data.split('_')[1]
                
                # Import here to avoid circular import
                from services.telegram_service import TelegramService
                if hasattr(self, 'handle_done_callback'):
                    self.handle_done_callback(symbol)
            
            elif callback_data.startswith('live_trade_'):
                parts = callback_data.split('_')
                if len(parts) >= 5:
                    symbol = parts[2]
                    signal_type = parts[3]
                    entry_price = parts[4]
                    
                    if hasattr(self, 'handle_live_trade_callback'):
                        self.handle_live_trade_callback(symbol, signal_type, entry_price)
            
            elif callback_data.startswith('auto_trade_'):
                parts = callback_data.split('_')
                if len(parts) >= 5:
                    symbol = parts[2]
                    signal_type = parts[3]
                    entry_price = parts[4]
                    
                    if hasattr(self, 'handle_auto_trade_callback'):
                        self.handle_auto_trade_callback(symbol, signal_type, entry_price)
                    
        except Exception as e:
            print(f"Error handling callback query: {str(e)}")
    
    def _send_message(self, message, extra_params=None):
        """Send text message"""
        try:
            # Validate configuration before sending
            if (not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN"):
                print("❌ Bot token not configured")
                return None
            
            if (not self.chat_id or self.chat_id == "YOUR_CHAT_ID"):
                print("❌ Chat ID not configured")
                return None
            
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            # Add extra parameters for broadcast mode
            if extra_params:
                data.update(extra_params)
            
            print(f"🔍 Sending message to chat_id: {self.chat_id}")
            response = requests.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    print(f"✅ Message sent successfully to {self.chat_id}")
                    return result
                else:
                    print(f"Telegram API error: {result}")
                    # Provide specific error guidance
                    if result.get('error_code') == 400 and 'chat not found' in result.get('description', ''):
                        print("💡 Solution: Chat ID is invalid or bot is not added to the chat")
                        print("   1. Make sure the bot is added to your chat/group")
                        print("   2. Send a message to the bot first")
                        print("   3. For groups: Add bot as admin or send /start command")
                        print("   4. Verify chat_id format (should be negative for groups)")
                        print(f"   5. Current chat_id: {self.chat_id}")
                    return None
            else:
                print(f"HTTP error {response.status_code}: {response.text}")
                # Parse error response for better debugging
                try:
                    error_data = response.json()
                    if error_data.get('error_code') == 400 and 'chat not found' in error_data.get('description', ''):
                        print("💡 Chat ID Error Solutions:")
                        print("   1. Verify bot is added to the chat/group")
                        print("   2. For private chat: Send /start to the bot first")
                        print("   3. For group chat: Add bot as member or admin")
                        print("   4. Check chat_id format:")
                        print(f"      - Private chat: positive number (123456789)")
                        print(f"      - Group chat: negative number (-123456789)")
                        print(f"      - Supergroup: -100 prefix (-100123456789)")
                        print(f"   5. Current chat_id: {self.chat_id}")
                        print("   6. Get correct chat_id from @userinfobot")
                except:
                    pass
                return None
            
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            return None
    
    def _send_photo_with_caption(self, image_bytes, caption, extra_params=None):
        """Send photo with caption"""
        try:
            # Validate configuration before sending
            if (not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN"):
                print("❌ Bot token not configured")
                return None
            
            if (not self.chat_id or self.chat_id == "YOUR_CHAT_ID"):
                print("❌ Chat ID not configured")
                return None
            
            url = f"{self.base_url}/sendPhoto"
            
            files = {
                'photo': ('chart.png', io.BytesIO(image_bytes), 'image/png')
            }
            
            data = {
                'chat_id': self.chat_id,
                'caption': caption,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            # Add extra parameters for broadcast mode
            if extra_params:
                data.update(extra_params)
            
            print(f"🔍 Sending photo to chat_id: {self.chat_id}")
            response = requests.post(url, files=files, data=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    print(f"✅ Photo sent successfully to {self.chat_id}")
                    return result
                else:
                    print(f"Telegram photo API error: {result}")
                    # Provide specific error guidance for photo
                    if result.get('error_code') == 400 and 'chat not found' in result.get('description', ''):
                        print("💡 Photo Send Error - Same chat_id issue as text messages")
                    return None
            else:
                print(f"HTTP error {response.status_code}: {response.text}")
                return None
            
        except Exception as e:
            print(f"Error sending photo: {str(e)}")
            return None
    
    def test_connection(self):
        """Test telegram bot connection"""
        try:
            # Validate configuration first
            if (not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN"):
                print("❌ Bot token not configured")
                return False
            
            if (not self.chat_id or self.chat_id == "YOUR_CHAT_ID"):
                print("❌ Chat ID not configured")
                return False
            
            print(f"🔍 Testing connection with chat_id: {self.chat_id}")
            
            # Send test message with broadcast mode info
            test_message = """
🤖 **CRYPTO SIGNAL BOT - ENHANCED TRACKING**

✅ **Connection Test Successful**

📢 **New Features:**
• 📈 Entry Button: Click to start TP/SL tracking
• 🎯 TP/SL Notifications: Get alerts when levels hit
• ✅ Done Button: Stop tracking anytime

🚫 **Important Notice:**
This bot operates in BROADCAST MODE ONLY.
The bot will NOT respond to messages or commands.

📈 **What you'll receive:**
• Automated trading signals with Entry buttons
• Real-time TP/SL hit notifications
• Technical analysis charts
• Interactive tracking system

⚠️ **Disclaimer:** 
All signals are for educational purposes only.
Always do your own research before trading.
            """
            
            # Test bot API
            url = f"{self.base_url}/getMe"
            response = requests.get(url)
            result = response.json()
            
            if result.get('ok'):
                print(f"Telegram bot connected: {result['result']['username']}")
                
                # Test chat access with a simple API call first
                chat_url = f"{self.base_url}/getChat"
                chat_response = requests.post(chat_url, data={'chat_id': self.chat_id})
                chat_result = chat_response.json()
                
                if not chat_result.get('ok'):
                    print(f"❌ Chat access test failed: {chat_result}")
                    if 'chat not found' in chat_result.get('description', ''):
                        print("💡 Chat ID Solutions:")
                        print("   1. Make sure bot is added to the chat/group")
                        print("   2. For private chat: Send /start to bot first")
                        print("   3. For group: Add bot as member/admin")
                        print("   4. Get correct chat_id from @userinfobot")
                        print(f"   5. Current chat_id: {self.chat_id}")
                        print("   6. Try these formats:")
                        print("      - Private: 123456789")
                        print("      - Group: -123456789")
                        print("      - Supergroup: -100123456789")
                    return False
                else:
                    print(f"✅ Chat access verified: {chat_result['result'].get('title', 'Private Chat')}")
                
                # Send enhanced info
                send_result = self._send_message(test_message.strip())
                
                if send_result:
                    print("✅ Test message sent successfully")
                    return True
                else:
                    print("❌ Failed to send test message")
                    return False
                
            else:
                print(f"Telegram bot error: {result}")
                return False
                
        except Exception as e:
            print(f"Error testing telegram connection: {str(e)}")
            return False
    
    def set_bot_description(self):
        """Set bot description for broadcast mode"""
        try:
            # Skip if not properly configured
            if (not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN"):
                return
            
            url = f"{self.base_url}/setMyDescription"
            data = {
                'description': """🤖 Enhanced Crypto Trading Signal Bot - BROADCAST MODE ONLY

📢 This bot sends automated trading signals with interactive TP/SL tracking.
🚫 Bot does not respond to messages or commands.
📈 Click "Entry" button to start tracking TP/SL levels.
🎯 Get notifications when TP/SL levels are hit.
✅ Click "Done" to stop tracking anytime.
⚠️ For educational purposes only - DYOR before trading."""
            }
            
            response = requests.post(url, data=data)
            if response.json().get('ok'):
                print("✅ Bot description set for enhanced broadcast mode")
            
        except Exception as e:
            print(f"Warning: Could not set bot description: {str(e)}")