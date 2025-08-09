#!/usr/bin/env python3
"""
Production version of app.py with enhanced configuration
"""
import os
import sys
import logging
from pathlib import Path

# Add project directory to Python path
project_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_dir))

# Set up production logging
def setup_production_logging():
    """Setup production logging"""
    log_dir = project_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "app.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from some libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

# Setup logging
setup_production_logging()

# Import production config
from production_config import ProductionConfig

# Ensure production directories
ProductionConfig.ensure_directories()

# Import main Flask app
from app import app

# Configure Flask for production
app.config['SECRET_KEY'] = ProductionConfig.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = ProductionConfig.MAX_CONTENT_LENGTH

# Add production error handling
@app.errorhandler(404)
def not_found_error(error):
    return {'error': 'Not found'}, 404

@app.errorhandler(500)
def internal_error(error):
    logging.error(f"Internal server error: {str(error)}")
    return {'error': 'Internal server error'}, 500

@app.before_first_request
def before_first_request():
    """Initialize production environment"""
    logging.info("🚀 Crypto Backtest Signal starting in production mode")
    logging.info(f"📁 Project directory: {project_dir}")
    logging.info(f"🐍 Python path: {sys.executable}")

if __name__ == '__main__':
    # This will only run if called directly (not via WSGI)
    print("🚀 Starting in development mode...")
    app.run(debug=False, host='0.0.0.0', port=5000)