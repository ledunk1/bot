#!/bin/bash
# Backup script for important data

echo "💾 Creating Backup..."

# Create backup directory
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

echo "📁 Backup directory: $BACKUP_DIR"

# Backup important files
echo "📋 Backing up configuration files..."
cp -r coin_settings $BACKUP_DIR/ 2>/dev/null || echo "⚠️ No coin_settings to backup"
cp -r trading_settings $BACKUP_DIR/ 2>/dev/null || echo "⚠️ No trading_settings to backup"
cp .env $BACKUP_DIR/ 2>/dev/null || echo "⚠️ No .env file to backup"
cp app.wsgi $BACKUP_DIR/ 2>/dev/null || echo "⚠️ No WSGI file to backup"

# Backup logs
echo "📋 Backing up logs..."
mkdir -p $BACKUP_DIR/logs
cp logs/*.log $BACKUP_DIR/logs/ 2>/dev/null || echo "⚠️ No logs to backup"

# Backup Apache config
echo "🌐 Backing up Apache configuration..."
sudo cp /etc/apache2/sites-available/crypto-backtest.conf $BACKUP_DIR/ 2>/dev/null || echo "⚠️ No Apache config to backup"

# Backup Supervisor config
echo "👥 Backing up Supervisor configuration..."
sudo cp /etc/supervisor/conf.d/crypto-backtest-worker.conf $BACKUP_DIR/ 2>/dev/null || echo "⚠️ No Supervisor config to backup"

# Create backup info
echo "📝 Creating backup info..."
cat > $BACKUP_DIR/backup_info.txt << EOF
Crypto Backtest Signal - Backup Information
==========================================

Backup Date: $(date)
Server IP: $(curl -s https://api.ipify.org 2>/dev/null || echo 'Unknown')
Project Directory: $(pwd)
Python Version: $(python3 --version)
System: $(uname -a)

Files Backed Up:
- Configuration files (coin_settings, trading_settings)
- Environment file (.env)
- WSGI configuration
- Application logs
- Apache virtual host config
- Supervisor worker config

Restore Instructions:
1. Copy files back to project directory
2. Set proper permissions: sudo chown -R www-data:www-data coin_settings trading_settings
3. Restart services: ./start.sh
EOF

# Compress backup
echo "🗜️ Compressing backup..."
tar -czf "${BACKUP_DIR}.tar.gz" -C backups $(basename $BACKUP_DIR)

# Remove uncompressed backup
rm -rf $BACKUP_DIR

echo ""
echo "✅ Backup completed!"
echo "📁 Backup file: ${BACKUP_DIR}.tar.gz"
echo "💾 Size: $(du -h ${BACKUP_DIR}.tar.gz | cut -f1)"

# Show backup list
echo ""
echo "📋 Available backups:"
ls -lah backups/*.tar.gz 2>/dev/null | tail -5 || echo "No previous backups found"