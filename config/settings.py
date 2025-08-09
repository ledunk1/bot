import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    BINANCE_API_URL = 'https://fapi.binance.com'
    
    # Default trading parameters
    DEFAULT_LEVERAGE = 10
    DEFAULT_MARGIN_PERCENT = 10
    DEFAULT_BALANCE = 10000
    
    # Supported intervals
    SUPPORTED_INTERVALS = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']
    
    # TA-lib indicator parameters
    RSI_PERIOD = 14
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    BB_PERIOD = 20
    BB_STD = 2
    EMA_FAST = 9
    EMA_SLOW = 21