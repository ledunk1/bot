#!/usr/bin/env python3
"""
Auto Deployment Script untuk Crypto Backtest Signal
Menjalankan setup otomatis untuk deployment ke VPS
"""

import os
import sys
import subprocess
import platform
import socket
import threading
import time
from pathlib import Path

class AutoDeployment:
    def __init__(self):
        self.system = platform.system().lower()
        self.is_vps = self.detect_vps_environment()
        self.public_ip = self.get_public_ip()
        self.local_ip = self.get_local_ip()
        
    def detect_vps_environment(self):
        """Deteksi apakah berjalan di VPS"""
        vps_indicators = [
            '/proc/user_beancounters',  # OpenVZ
            '/proc/vz',                 # Virtuozzo
            '/sys/class/dmi/id/product_name'  # Check for VPS signatures
        ]
        
        for indicator in vps_indicators:
            if os.path.exists(indicator):
                return True
                
        # Check for common VPS hostnames
        hostname = socket.gethostname().lower()
        vps_keywords = ['vps', 'cloud', 'server', 'host', 'vm']
        
        return any(keyword in hostname for keyword in vps_keywords)
    
    def get_public_ip(self):
        """Dapatkan IP publik"""
        try:
            import requests
            response = requests.get('https://api.ipify.org', timeout=5)
            return response.text.strip()
        except:
            try:
                response = requests.get('https://httpbin.org/ip', timeout=5)
                return response.json()['origin']
            except:
                return "Unable to detect"
    
    def get_local_ip(self):
        """Dapatkan IP lokal"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def install_dependencies(self):
        """Install dependencies yang diperlukan"""
        print("🔧 Installing system dependencies...")
        
        if self.system == 'linux':
            # Update package list
            subprocess.run(['sudo', 'apt', 'update'], check=False)
            
            # Install required packages
            packages = [
                'python3-pip',
                'python3-venv',
                'nginx',
                'supervisor',
                'ufw',
                'curl',
                'wget',
                'git'
            ]
            
            for package in packages:
                print(f"Installing {package}...")
                subprocess.run(['sudo', 'apt', 'install', '-y', package], check=False)
        
        # Install Python dependencies
        print("📦 Installing Python dependencies...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], check=False)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=False)
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'gunicorn', 'gevent'], check=False)
    
    def setup_firewall(self):
        """Setup firewall untuk keamanan"""
        if self.system == 'linux' and self.is_vps:
            print("🔒 Setting up firewall...")
            
            # Enable UFW
            subprocess.run(['sudo', 'ufw', '--force', 'enable'], check=False)
            
            # Allow SSH
            subprocess.run(['sudo', 'ufw', 'allow', 'ssh'], check=False)
            
            # Allow HTTP and HTTPS
            subprocess.run(['sudo', 'ufw', 'allow', '80'], check=False)
            subprocess.run(['sudo', 'ufw', 'allow', '443'], check=False)
            
            # Allow Flask port
            subprocess.run(['sudo', 'ufw', 'allow', '5000'], check=False)
            
            print("✅ Firewall configured")
    
    def create_nginx_config(self):
        """Buat konfigurasi Nginx"""
        if self.system == 'linux':
            nginx_config = f"""
server {{
    listen 80;
    server_name {self.public_ip} {self.local_ip} localhost;
    
    location / {{
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}
    
    location /static {{
        alias {os.getcwd()}/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }}
}}
"""
            
            config_path = '/etc/nginx/sites-available/crypto-backtest'
            
            try:
                with open(config_path, 'w') as f:
                    f.write(nginx_config)
                
                # Enable site
                subprocess.run(['sudo', 'ln', '-sf', config_path, '/etc/nginx/sites-enabled/'], check=False)
                
                # Remove default site
                subprocess.run(['sudo', 'rm', '-f', '/etc/nginx/sites-enabled/default'], check=False)
                
                # Test and reload nginx
                subprocess.run(['sudo', 'nginx', '-t'], check=False)
                subprocess.run(['sudo', 'systemctl', 'reload', 'nginx'], check=False)
                subprocess.run(['sudo', 'systemctl', 'enable', 'nginx'], check=False)
                
                print("✅ Nginx configured")
                
            except PermissionError:
                print("⚠️ Need sudo access to configure Nginx")
                print(f"Please run: sudo tee {config_path} << 'EOF'")
                print(nginx_config)
                print("EOF")
    
    def create_supervisor_config(self):
        """Buat konfigurasi Supervisor untuk auto-restart"""
        if self.system == 'linux':
            supervisor_config = f"""
[program:crypto-backtest]
command={sys.executable} {os.getcwd()}/app.py
directory={os.getcwd()}
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/crypto-backtest.log
environment=PYTHONPATH="{os.getcwd()}"
"""
            
            config_path = '/etc/supervisor/conf.d/crypto-backtest.conf'
            
            try:
                with open(config_path, 'w') as f:
                    f.write(supervisor_config)
                
                # Reload supervisor
                subprocess.run(['sudo', 'supervisorctl', 'reread'], check=False)
                subprocess.run(['sudo', 'supervisorctl', 'update'], check=False)
                subprocess.run(['sudo', 'supervisorctl', 'start', 'crypto-backtest'], check=False)
                
                print("✅ Supervisor configured")
                
            except PermissionError:
                print("⚠️ Need sudo access to configure Supervisor")
    
    def create_systemd_service(self):
        """Buat systemd service sebagai alternatif"""
        if self.system == 'linux':
            service_config = f"""
[Unit]
Description=Crypto Backtest Signal App
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory={os.getcwd()}
Environment=PYTHONPATH={os.getcwd()}
ExecStart={sys.executable} {os.getcwd()}/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
            
            service_path = '/etc/systemd/system/crypto-backtest.service'
            
            try:
                with open(service_path, 'w') as f:
                    f.write(service_config)
                
                # Enable and start service
                subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=False)
                subprocess.run(['sudo', 'systemctl', 'enable', 'crypto-backtest'], check=False)
                subprocess.run(['sudo', 'systemctl', 'start', 'crypto-backtest'], check=False)
                
                print("✅ Systemd service configured")
                
            except PermissionError:
                print("⚠️ Need sudo access to configure Systemd service")
    
    def setup_ssl_certificate(self):
        """Setup SSL certificate dengan Let's Encrypt (opsional)"""
        if self.system == 'linux' and self.is_vps:
            print("🔐 SSL Certificate setup available...")
            print("To enable HTTPS, run after deployment:")
            print("sudo apt install certbot python3-certbot-nginx")
            print(f"sudo certbot --nginx -d {self.public_ip}")
    
    def create_startup_script(self):
        """Buat script startup untuk development"""
        startup_script = f"""#!/bin/bash
# Crypto Backtest Signal - Startup Script

echo "🚀 Starting Crypto Backtest Signal..."

# Set environment variables
export FLASK_APP=app.py
export FLASK_ENV=production
export PYTHONPATH="{os.getcwd()}"

# Create necessary directories
mkdir -p optimizer_cache
mkdir -p coin_settings
mkdir -p logs

# Start the application
if command -v gunicorn &> /dev/null; then
    echo "Starting with Gunicorn..."
    gunicorn --bind 0.0.0.0:5000 --workers 4 --worker-class gevent --worker-connections 1000 app:app
else
    echo "Starting with Flask development server..."
    python3 app.py
fi
"""
        
        with open('start.sh', 'w') as f:
            f.write(startup_script)
        
        os.chmod('start.sh', 0o755)
        print("✅ Startup script created: start.sh")
    
    def display_access_info(self):
        """Tampilkan informasi akses"""
        print("\n" + "="*60)
        print("🎉 DEPLOYMENT COMPLETED!")
        print("="*60)
        print(f"🌐 Public IP: {self.public_ip}")
        print(f"🏠 Local IP: {self.local_ip}")
        print("\n📱 Access URLs:")
        print(f"   • http://{self.public_ip}")
        print(f"   • http://{self.local_ip}")
        print(f"   • http://localhost:5000")
        
        if self.is_vps:
            print(f"\n🔗 VPS Access:")
            print(f"   • Main: http://{self.public_ip}")
            print(f"   • Backup: http://{self.public_ip}:5000")
        
        print(f"\n📊 Available Pages:")
        print(f"   • Main Backtest: /")
        print(f"   • Live Scanner: /live")
        print(f"   • Optimizer: /optimizer")
        
        print(f"\n🔧 Management Commands:")
        if self.system == 'linux':
            print(f"   • Check status: sudo systemctl status crypto-backtest")
            print(f"   • Restart: sudo systemctl restart crypto-backtest")
            print(f"   • View logs: sudo journalctl -u crypto-backtest -f")
            print(f"   • Nginx status: sudo systemctl status nginx")
        
        print(f"\n📝 Log Files:")
        print(f"   • App logs: /var/log/crypto-backtest.log")
        print(f"   • Nginx logs: /var/log/nginx/")
        
        print("\n⚠️  Important Notes:")
        print("   • Make sure to configure .env file with your Telegram credentials")
        print("   • Firewall is configured to allow HTTP/HTTPS traffic")
        print("   • Application will auto-restart on system reboot")
        print("="*60)
    
    def run_deployment(self):
        """Jalankan proses deployment lengkap"""
        print("🚀 Starting Auto Deployment for Crypto Backtest Signal")
        print(f"📍 System: {self.system}")
        print(f"🖥️  VPS Detected: {self.is_vps}")
        print(f"🌐 Public IP: {self.public_ip}")
        print(f"🏠 Local IP: {self.local_ip}")
        print("-" * 60)
        
        try:
            # Step 1: Install dependencies
            self.install_dependencies()
            
            # Step 2: Setup firewall
            self.setup_firewall()
            
            # Step 3: Create startup script
            self.create_startup_script()
            
            # Step 4: Configure web server (if VPS)
            if self.is_vps and self.system == 'linux':
                self.create_nginx_config()
                self.create_supervisor_config()
                self.create_systemd_service()
                self.setup_ssl_certificate()
            
            # Step 5: Display access information
            self.display_access_info()
            
            return True
            
        except Exception as e:
            print(f"❌ Deployment failed: {str(e)}")
            return False

def main():
    """Main function"""
    print("🔧 Crypto Backtest Signal - Auto Deployment")
    print("=" * 50)
    
    # Check if running as root for VPS setup
    if os.geteuid() != 0 and platform.system().lower() == 'linux':
        print("⚠️  For full VPS setup, please run with sudo:")
        print("sudo python3 deploy.py")
        print("\nContinuing with limited setup...")
    
    # Run deployment
    deployer = AutoDeployment()
    success = deployer.run_deployment()
    
    if success:
        print("\n✅ Deployment completed successfully!")
        
        # Ask if user wants to start the application
        try:
            start_now = input("\n🚀 Start the application now? (y/n): ").lower().strip()
            if start_now in ['y', 'yes']:
                print("Starting application...")
                if os.path.exists('start.sh'):
                    os.system('./start.sh')
                else:
                    os.system('python3 app.py')
        except KeyboardInterrupt:
            print("\n👋 Deployment completed. Run './start.sh' to start the application.")
    else:
        print("\n❌ Deployment failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()