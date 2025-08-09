#!/bin/bash
# Real-time monitoring script

echo "📊 Real-time Monitoring - Crypto Backtest Signal"
echo "==============================================="

# Function to get service status
get_status() {
    local service=$1
    if systemctl is-active --quiet $service; then
        echo "✅ $service"
    else
        echo "❌ $service"
    fi
}

# Function to get process info
get_process_info() {
    echo "🔄 Apache Processes:"
    ps aux | grep apache2 | grep -v grep | wc -l | xargs echo "   Active processes:"
    
    echo "👥 Supervisor Processes:"
    sudo supervisorctl status | grep crypto-backtest
}

# Function to get resource usage
get_resources() {
    echo "💾 Memory Usage:"
    free -h | grep '^Mem:' | awk '{print "   Used: " $3 " / " $2 " (" $3/$2*100 "%)"}'
    
    echo "💿 Disk Usage:"
    df -h $(pwd) | tail -1 | awk '{print "   Used: " $3 " / " $2 " (" $5 ")"}'
    
    echo "⚡ CPU Load:"
    uptime | awk -F'load average:' '{print "   Load:" $2}'
}

# Function to get network info
get_network() {
    echo "🌐 Network Status:"
    echo "   Public IP: $(curl -s https://api.ipify.org 2>/dev/null || echo 'Unable to detect')"
    echo "   Local IP: $(hostname -I | awk '{print $1}')"
    
    echo "🔥 Firewall Status:"
    sudo ufw status | grep -E "(Status|80|443)" | head -3
}

# Function to get log info
get_logs() {
    echo "📋 Recent Logs (last 5 lines):"
    echo "   Apache Error Log:"
    sudo tail -5 /var/log/apache2/crypto-backtest_error.log 2>/dev/null | sed 's/^/     /'
    
    echo "   Application Log:"
    tail -5 logs/app.log 2>/dev/null | sed 's/^/     /' || echo "     No application logs found"
}

# Main monitoring loop
while true; do
    clear
    echo "📊 Real-time Monitoring - $(date)"
    echo "==============================================="
    
    echo "🔧 Service Status:"
    get_status apache2
    get_status supervisor
    
    echo ""
    get_process_info
    
    echo ""
    get_resources
    
    echo ""
    get_network
    
    echo ""
    get_logs
    
    echo ""
    echo "🔄 Refreshing in 30 seconds... (Ctrl+C to exit)"
    echo "💡 Commands: ./start.sh | ./stop.sh | ./status.sh"
    
    sleep 30
done