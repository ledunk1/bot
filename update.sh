#!/bin/bash
# Update script for production deployment

echo "🔄 Updating Crypto Backtest Signal"
echo "=================================="

# Backup current state
echo "💾 Creating backup before update..."
./backup.sh

# Stop services
echo "🛑 Stopping services..."
sudo systemctl stop apache2
sudo supervisorctl stop crypto-backtest-worker

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Update Python packages (if needed)
echo "📦 Checking for package updates..."
pip list --outdated

# Set proper permissions
echo "🔐 Setting permissions..."
sudo chown -R www-data:$(whoami) .
sudo chmod -R 755 .

# Ensure directories exist
mkdir -p optimizer_cache coin_settings trading_settings logs
sudo chown -R www-data:www-data optimizer_cache coin_settings trading_settings logs

# Reload Apache configuration
echo "🌐 Reloading Apache configuration..."
sudo apache2ctl configtest
if [ $? -eq 0 ]; then
    sudo systemctl reload apache2
else
    echo "❌ Apache configuration test failed!"
    exit 1
fi

# Reload Supervisor configuration
echo "👥 Reloading Supervisor configuration..."
sudo supervisorctl reread
sudo supervisorctl update

# Start services
echo "🚀 Starting services..."
sudo systemctl start apache2
sudo supervisorctl start crypto-backtest-worker

# Check status
echo "📊 Checking service status..."
./status.sh

echo ""
echo "✅ Update completed!"
echo "🌐 Access at: http://$(curl -s https://api.ipify.org 2>/dev/null)"