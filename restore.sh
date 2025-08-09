#!/bin/bash
# Restore script from backup

echo "🔄 Restore from Backup"
echo "====================="

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "Usage: ./restore.sh backup_file.tar.gz"
    echo ""
    echo "📋 Available backups:"
    ls -lah backups/*.tar.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE=$1

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "📁 Restoring from: $BACKUP_FILE"

# Create temporary restore directory
TEMP_DIR="temp_restore_$(date +%s)"
mkdir -p $TEMP_DIR

# Extract backup
echo "📦 Extracting backup..."
tar -xzf $BACKUP_FILE -C $TEMP_DIR

# Find the backup directory
BACKUP_DIR=$(find $TEMP_DIR -maxdepth 2 -type d -name "20*" | head -1)

if [ -z "$BACKUP_DIR" ]; then
    echo "❌ Invalid backup file structure"
    rm -rf $TEMP_DIR
    exit 1
fi

echo "📂 Found backup directory: $BACKUP_DIR"

# Stop services before restore
echo "🛑 Stopping services..."
sudo systemctl stop apache2
sudo supervisorctl stop crypto-backtest-worker

# Restore files
echo "🔄 Restoring files..."

# Restore configuration directories
if [ -d "$BACKUP_DIR/coin_settings" ]; then
    cp -r $BACKUP_DIR/coin_settings .
    sudo chown -R www-data:www-data coin_settings
    echo "✅ Restored coin_settings"
fi

if [ -d "$BACKUP_DIR/trading_settings" ]; then
    cp -r $BACKUP_DIR/trading_settings .
    sudo chown -R www-data:www-data trading_settings
    echo "✅ Restored trading_settings"
fi

# Restore .env file
if [ -f "$BACKUP_DIR/.env" ]; then
    cp $BACKUP_DIR/.env .
    chmod 600 .env
    echo "✅ Restored .env file"
fi

# Restore WSGI file
if [ -f "$BACKUP_DIR/app.wsgi" ]; then
    cp $BACKUP_DIR/app.wsgi .
    chmod 755 app.wsgi
    echo "✅ Restored WSGI file"
fi

# Restore Apache config
if [ -f "$BACKUP_DIR/crypto-backtest.conf" ]; then
    sudo cp $BACKUP_DIR/crypto-backtest.conf /etc/apache2/sites-available/
    echo "✅ Restored Apache config"
fi

# Restore Supervisor config
if [ -f "$BACKUP_DIR/crypto-backtest-worker.conf" ]; then
    sudo cp $BACKUP_DIR/crypto-backtest-worker.conf /etc/supervisor/conf.d/
    sudo supervisorctl reread
    sudo supervisorctl update
    echo "✅ Restored Supervisor config"
fi

# Cleanup
rm -rf $TEMP_DIR

# Start services
echo "🚀 Starting services..."
sudo systemctl start apache2
sudo supervisorctl start crypto-backtest-worker

echo ""
echo "✅ Restore completed!"
echo "📊 Run ./status.sh to check service status"
echo "🌐 Access at: http://$(curl -s https://api.ipify.org 2>/dev/null)"