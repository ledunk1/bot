import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class EnvConfig:
    """Environment configuration class"""
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # Binance API Configuration for Trading
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
    BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
    
    # Binance Configuration
    # Production Binance URLs only
    BINANCE_WS_URL = os.getenv('BINANCE_WS_URL', 'wss://fstream.binance.com/ws/')
    BINANCE_API_URL = os.getenv('BINANCE_API_URL', 'https://fapi.binance.com')
    
    # Scanner Settings
    MIN_SIGNAL_STRENGTH = float(os.getenv('MIN_SIGNAL_STRENGTH', '0.3'))
    MAX_SYMBOLS = int(os.getenv('MAX_SYMBOLS', '50'))
    SCAN_INTERVAL = int(os.getenv('SCAN_INTERVAL', '300'))
    
    # Chart Settings
    CHART_UPDATE_INTERVAL = int(os.getenv('CHART_UPDATE_INTERVAL', '5000'))
    LIVE_DATA_CACHE_DURATION = int(os.getenv('LIVE_DATA_CACHE_DURATION', '60'))
    
    @classmethod
    def validate_telegram_config(cls):
        """Validate Telegram configuration"""
        if not cls.TELEGRAM_BOT_TOKEN or cls.TELEGRAM_BOT_TOKEN == '':
            return False, "TELEGRAM_BOT_TOKEN must be configured in .env file. Get it from @BotFather"
        
        if not cls.TELEGRAM_CHAT_ID or cls.TELEGRAM_CHAT_ID == '':
            return False, "TELEGRAM_CHAT_ID must be configured in .env file. Get it from @userinfobot"
        
        # Validate bot token format
        if ':' not in cls.TELEGRAM_BOT_TOKEN or len(cls.TELEGRAM_BOT_TOKEN) < 35:
            return False, "Invalid bot token format. Should be like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        
        # Validate chat ID format
        try:
            chat_id_int = int(cls.TELEGRAM_CHAT_ID)
            if chat_id_int == 0:
                return False, "Chat ID cannot be 0. Get correct chat_id from @userinfobot"
        except ValueError:
            return False, "Chat ID must be a number. Get it from @userinfobot"
        
        return True, "Telegram configuration is valid"
    
    @classmethod
    def get_telegram_config(cls):
        """Get Telegram configuration"""
        return {
            'bot_token': cls.TELEGRAM_BOT_TOKEN,
            'chat_id': cls.TELEGRAM_CHAT_ID
        }
    
    @classmethod
    def get_binance_config(cls):
        """Get Binance API configuration"""
        return {
            'api_key': cls.BINANCE_API_KEY,
            'api_secret': cls.BINANCE_API_SECRET
        }
    
    @classmethod
    def validate_binance_config(cls):
        """Validate Binance API configuration"""
        if not cls.BINANCE_API_KEY or cls.BINANCE_API_KEY == '':
            return False, "BINANCE_API_KEY must be configured in .env file"
        
        if not cls.BINANCE_API_SECRET or cls.BINANCE_API_SECRET == '':
            return False, "BINANCE_API_SECRET must be configured in .env file"
        
        # Validate API key format
        if len(cls.BINANCE_API_KEY) != 64:
            return False, "Invalid API key format. Should be exactly 64 characters"
        
        if len(cls.BINANCE_API_SECRET) != 64:
            return False, "Invalid API secret format. Should be exactly 64 characters"
        
        return True, "Binance API configuration is valid"