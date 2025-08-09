"""
Production configuration for Apache + WSGI deployment
"""
import os
from pathlib import Path

class ProductionConfig:
    """Production configuration settings"""
    
    # Project paths
    PROJECT_ROOT = Path(__file__).parent.absolute()
    VENV_PATH = PROJECT_ROOT / "venv"
    PYTHON_PATH = VENV_PATH / "bin" / "python"
    
    # Apache/WSGI settings
    WSGI_PROCESSES = 4
    WSGI_THREADS = 2
    WSGI_MAX_REQUESTS = 1000
    
    # Security settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'production-secret-key-change-this'
    
    # Cache settings
    CACHE_TIMEOUT = 300  # 5 minutes
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = PROJECT_ROOT / "logs" / "app.log"
    
    # Performance settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
    
    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist"""
        directories = [
            cls.PROJECT_ROOT / "logs",
            cls.PROJECT_ROOT / "optimizer_cache",
            cls.PROJECT_ROOT / "coin_settings",
            cls.PROJECT_ROOT / "trading_settings"
        ]
        
        for directory in directories:
            directory.mkdir(exist_ok=True)
            
        print("✅ Production directories ensured")
    
    @classmethod
    def get_wsgi_config(cls):
        """Get WSGI configuration"""
        return {
            'processes': cls.WSGI_PROCESSES,
            'threads': cls.WSGI_THREADS,
            'max_requests': cls.WSGI_MAX_REQUESTS,
            'python_home': str(cls.VENV_PATH),
            'python_path': str(cls.PROJECT_ROOT)
        }