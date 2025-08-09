import time
import threading
from datetime import datetime
from services.live_data_service import LiveDataService
from services.telegram_service import TelegramService

class LiveScannerService:
    def __init__(self, telegram_bot_token=None, telegram_chat_id=None):
        self.live_data_service = LiveDataService()
        self.telegram_service = TelegramService(telegram_bot_token, telegram_chat_id)
        self.is_running = False
        self.scan_thread = None
        self.scan_interval = 300  # 5 minutes
        self.min_signal_strength = 0.3
        self.sent_signals = set()  # Track sent signals to avoid duplicates
        
    def start_scanner(self):
        """Start the live scanner"""
        if self.is_running:
            print("Scanner is already running")
            return
        
        print("Starting live scanner...")
        self.is_running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        
        # Test telegram connection
        if not self.telegram_service.test_connection():
            print("Warning: Telegram connection failed. Notifications will not be sent.")
    
    def stop_scanner(self):
        """Stop the live scanner"""
        print("Stopping live scanner...")
        self.is_running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=10)
    
    def _scan_loop(self):
        """Main scanning loop"""
        while self.is_running:
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting scan...")
                
                # Scan for signals
                signals = self.live_data_service.scan_all_symbols(
                    interval='1h',
                    min_signal_strength=self.min_signal_strength
                )
                
                # Process new signals
                new_signals = self._filter_new_signals(signals)
                
                if new_signals:
                    print(f"Found {len(new_signals)} new signals")
                    
                    for signal in new_signals:
                        try:
                            # Send telegram notification
                            success = self.telegram_service.send_signal_notification(signal)
                            
                            if success:
                                print(f"Sent notification for {signal['symbol']} - {signal['signal']}")
                                # Mark as sent
                                signal_key = f"{signal['symbol']}_{signal['signal']}_{signal['timestamp']}"
                                self.sent_signals.add(signal_key)
                            else:
                                print(f"Failed to send notification for {signal['symbol']}")
                                
                        except Exception as e:
                            print(f"Error processing signal {signal['symbol']}: {str(e)}")
                else:
                    print("No new signals found")
                
                # Clean old sent signals (older than 1 hour)
                self._clean_old_signals()
                
                print(f"Scan completed. Next scan in {self.scan_interval} seconds.")
                
                # Wait for next scan
                for _ in range(self.scan_interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Error in scan loop: {str(e)}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _filter_new_signals(self, signals):
        """Filter out already sent signals"""
        new_signals = []
        
        for signal in signals:
            signal_key = f"{signal['symbol']}_{signal['signal']}_{signal['timestamp']}"
            
            if signal_key not in self.sent_signals:
                new_signals.append(signal)
        
        return new_signals
    
    def _clean_old_signals(self):
        """Clean old sent signals to prevent memory buildup"""
        current_time = datetime.now()
        
        # Keep only signals from last hour
        signals_to_remove = []
        for signal_key in self.sent_signals:
            try:
                # Extract timestamp from signal key
                timestamp_str = signal_key.split('_')[-1]
                signal_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                # Remove if older than 1 hour
                if (current_time - signal_time.replace(tzinfo=None)).total_seconds() > 3600:
                    signals_to_remove.append(signal_key)
            except:
                # Remove invalid signal keys
                signals_to_remove.append(signal_key)
        
        for signal_key in signals_to_remove:
            self.sent_signals.discard(signal_key)
    
    def get_status(self):
        """Get scanner status"""
        return {
            'is_running': self.is_running,
            'scan_interval': self.scan_interval,
            'min_signal_strength': self.min_signal_strength,
            'sent_signals_count': len(self.sent_signals)
        }
    
    def update_settings(self, scan_interval=None, min_signal_strength=None):
        """Update scanner settings"""
        if scan_interval is not None:
            self.scan_interval = max(60, scan_interval)  # Minimum 1 minute
            
        if min_signal_strength is not None:
            self.min_signal_strength = max(0.1, min(1.0, min_signal_strength))
        
        print(f"Scanner settings updated: interval={self.scan_interval}s, min_strength={self.min_signal_strength}")