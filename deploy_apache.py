#!/usr/bin/env python3
"""
Ubuntu Apache WSGI Auto Deployment Script
Setup otomatis untuk production deployment dengan Apache + mod_wsgi
"""

import os
import sys
import subprocess
import platform
import socket
import getpass
from pathlib import Path

class UbuntuApacheDeployment:
    def __init__(self):
        self.project_dir = os.getcwd()
        self.project_name = "crypto-backtest"
        self.user = getpass.getuser()
        self.public_ip = self.get_public_ip()
        self.local_ip = self.get_local_ip()
        self.venv_path = os.path.join(self.project_dir, "venv")
        self.python_path = os.path.join(self.venv_path, "bin", "python")
        
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
    
    def check_root_privileges(self):
        """Check if running with sudo privileges"""
        if os.geteuid() != 0:
            print("❌ This script requires sudo privileges for Apache configuration")
            print("Please run: sudo python3 deploy_apache.py")
            sys.exit(1)
    
    def install_system_packages(self):
        """Install required system packages"""
        print("🔧 Installing system packages...")
        
        packages = [
            'apache2',
            'libapache2-mod-wsgi-py3',
            'python3-venv',
            'python3-pip',
            'supervisor',
            'ufw'
        ]
        
        # Update package list
        subprocess.run(['apt', 'update'], check=True)
        
        # Install packages
        for package in packages:
            print(f"Installing {package}...")
            result = subprocess.run(['apt', 'install', '-y', package], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"⚠️ Warning: Failed to install {package}")
                print(f"Error: {result.stderr}")
    
    def create_virtual_environment(self):
        """Create virtual environment"""
        print("🐍 Creating virtual environment...")
        
        if os.path.exists(self.venv_path):
            print(f"Virtual environment already exists at {self.venv_path}")
            return
        
        # Create virtual environment
        subprocess.run([
            'python3', '-m', 'venv', self.venv_path
        ], check=True)
        
        print(f"✅ Virtual environment created at {self.venv_path}")
        print(f"📝 To activate manually: source {self.venv_path}/bin/activate")
        print(f"📝 Python path: {self.python_path}")
    
    def create_wsgi_file(self):
        """Create WSGI application file"""
        print("📄 Creating WSGI application file...")
        
        wsgi_content = f'''#!/usr/bin/env python3
"""
WSGI Application for Crypto Backtest Signal
"""
import sys
import os

# Add project directory to Python path
project_dir = '{self.project_dir}'
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Set environment variables
os.environ['PYTHONPATH'] = project_dir

# Change to project directory
os.chdir(project_dir)

# Import Flask application
from app import app as application

if __name__ == "__main__":
    application.run()
'''
        
        wsgi_file = os.path.join(self.project_dir, "app.wsgi")
        with open(wsgi_file, 'w') as f:
            f.write(wsgi_content)
        
        # Make executable
        os.chmod(wsgi_file, 0o755)
        print(f"✅ WSGI file created: {wsgi_file}")
    
    def create_apache_vhost(self):
        """Create Apache virtual host configuration"""
        print("🌐 Creating Apache virtual host...")
        
        vhost_content = f'''<VirtualHost *:80>
    ServerName {self.public_ip}
    ServerAlias {self.local_ip} localhost
    DocumentRoot {self.project_dir}
    
    WSGIDaemonProcess {self.project_name} python-home={self.venv_path} python-path={self.project_dir}
    WSGIProcessGroup {self.project_name}
    WSGIScriptAlias / {self.project_dir}/app.wsgi
    
    <Directory {self.project_dir}>
        WSGIApplicationGroup %{{GLOBAL}}
        Require all granted
    </Directory>
    
    # Static files
    Alias /static {self.project_dir}/static
    <Directory {self.project_dir}/static>
        Require all granted
        ExpiresActive On
        ExpiresDefault "access plus 1 year"
    </Directory>
    
    # Logs
    ErrorLog ${{APACHE_LOG_DIR}}/{self.project_name}_error.log
    CustomLog ${{APACHE_LOG_DIR}}/{self.project_name}_access.log combined
    LogLevel info
    
    # Security headers
    Header always set X-Content-Type-Options nosniff
    Header always set X-Frame-Options DENY
    Header always set X-XSS-Protection "1; mode=block"
    
    # WSGI Configuration
    WSGIScriptReloading On
    WSGIApplicationGroup %{{GLOBAL}}
</VirtualHost>'''
        
        vhost_file = f'/etc/apache2/sites-available/{self.project_name}.conf'
        
        with open(vhost_file, 'w') as f:
            f.write(vhost_content)
        
        print(f"✅ Apache vhost created: {vhost_file}")
        return vhost_file
    
    def configure_apache(self):
        """Configure Apache server"""
        print("⚙️ Configuring Apache...")
        
        # Enable required modules
        modules = ['wsgi', 'rewrite', 'headers', 'expires']
        for module in modules:
            subprocess.run(['a2enmod', module], check=False)
        
        # Create and enable site
        vhost_file = self.create_apache_vhost()
        
        # Disable default site
        subprocess.run(['a2dissite', '000-default'], check=False)
        
        # Enable our site
        subprocess.run(['a2ensite', self.project_name], check=True)
        
        # Test Apache configuration
        result = subprocess.run(['apache2ctl', 'configtest'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️ Apache config test failed: {result.stderr}")
        else:
            print("✅ Apache configuration test passed")
        
        # Set proper permissions
        self.set_permissions()
        
        # Restart Apache
        subprocess.run(['systemctl', 'restart', 'apache2'], check=True)
        subprocess.run(['systemctl', 'enable', 'apache2'], check=True)
        
        print("✅ Apache configured and restarted")
    
    def set_permissions(self):
        """Set proper file permissions"""
        print("🔐 Setting file permissions...")
        
        # Set ownership to www-data for Apache
        subprocess.run(['chown', '-R', f'www-data:{self.user}', self.project_dir], check=False)
        
        # Set directory permissions
        subprocess.run(['chmod', '-R', '755', self.project_dir], check=False)
        
        # Set specific permissions for sensitive files
        subprocess.run(['chmod', '644', os.path.join(self.project_dir, 'app.wsgi')], check=False)
        
        # Create necessary directories with proper permissions
        dirs_to_create = [
            'optimizer_cache',
            'coin_settings', 
            'trading_settings',
            'logs'
        ]
        
        for dir_name in dirs_to_create:
            dir_path = os.path.join(self.project_dir, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            subprocess.run(['chown', '-R', 'www-data:www-data', dir_path], check=False)
            subprocess.run(['chmod', '-R', '755', dir_path], check=False)
        
        print("✅ Permissions set")
    
    def create_supervisor_config(self):
        """Create Supervisor configuration for background tasks"""
        print("👥 Creating Supervisor configuration...")
        
        supervisor_config = f'''[program:{self.project_name}-worker]
command={self.python_path} -c "
import sys
sys.path.insert(0, '{self.project_dir}')
import time
print('Background worker started for {self.project_name}')
while True:
    time.sleep(60)
    # Add any background tasks here if needed
"
directory={self.project_dir}
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/{self.project_name}-worker.log
environment=PYTHONPATH="{self.project_dir}"
'''
        
        config_file = f'/etc/supervisor/conf.d/{self.project_name}-worker.conf'
        
        with open(config_file, 'w') as f:
            f.write(supervisor_config)
        
        # Reload supervisor
        subprocess.run(['supervisorctl', 'reread'], check=False)
        subprocess.run(['supervisorctl', 'update'], check=False)
        subprocess.run(['supervisorctl', 'start', f'{self.project_name}-worker'], check=False)
        
        print(f"✅ Supervisor configuration created: {config_file}")
    
    def setup_firewall(self):
        """Setup UFW firewall"""
        print("🔒 Configuring firewall...")
        
        # Enable UFW
        subprocess.run(['ufw', '--force', 'enable'], check=False)
        
        # Allow essential ports
        ports = ['22', '80', '443']  # SSH, HTTP, HTTPS
        for port in ports:
            subprocess.run(['ufw', 'allow', port], check=False)
            print(f"Allowed port {port}")
        
        # Show status
        result = subprocess.run(['ufw', 'status'], capture_output=True, text=True)
        print("Firewall status:")
        print(result.stdout)
    
    def create_startup_script(self):
        """Create startup script for manual management"""
        print("📜 Creating management scripts...")
        
        # Start script
        start_script = f'''#!/bin/bash
# Crypto Backtest Signal - Start Script

echo "🚀 Starting Crypto Backtest Signal (Apache + WSGI)..."

# Activate virtual environment
source {self.venv_path}/bin/activate

# Set environment variables
export PYTHONPATH="{self.project_dir}"
export FLASK_ENV=production

# Create necessary directories
mkdir -p {self.project_dir}/optimizer_cache
mkdir -p {self.project_dir}/coin_settings
mkdir -p {self.project_dir}/trading_settings
mkdir -p {self.project_dir}/logs

# Set permissions
sudo chown -R www-data:www-data {self.project_dir}/optimizer_cache
sudo chown -R www-data:www-data {self.project_dir}/coin_settings
sudo chown -R www-data:www-data {self.project_dir}/trading_settings
sudo chown -R www-data:www-data {self.project_dir}/logs

# Start Apache
sudo systemctl start apache2
sudo systemctl start supervisor

echo "✅ Services started!"
echo "🌐 Access at: http://{self.public_ip}"
'''
        
        # Stop script
        stop_script = f'''#!/bin/bash
# Crypto Backtest Signal - Stop Script

echo "🛑 Stopping Crypto Backtest Signal..."

# Stop services
sudo systemctl stop apache2
sudo supervisorctl stop {self.project_name}-worker

echo "✅ Services stopped!"
'''
        
        # Status script
        status_script = f'''#!/bin/bash
# Crypto Backtest Signal - Status Script

echo "📊 Crypto Backtest Signal Status"
echo "================================"

echo "🌐 Apache Status:"
sudo systemctl status apache2 --no-pager -l

echo ""
echo "👥 Supervisor Status:"
sudo supervisorctl status

echo ""
echo "🔥 Firewall Status:"
sudo ufw status

echo ""
echo "📊 System Resources:"
echo "Memory: $(free -h | grep '^Mem:' | awk '{{print $3 "/" $2}}')"
echo "Disk: $(df -h {self.project_dir} | tail -1 | awk '{{print $3 "/" $2 " (" $5 " used)"}}')"
echo "Load: $(uptime | awk -F'load average:' '{{print $2}}')"

echo ""
echo "🌐 Access URLs:"
echo "  • http://{self.public_ip}"
echo "  • http://{self.local_ip}"
echo "  • http://localhost"
'''
        
        # Write scripts
        scripts = {
            'start.sh': start_script,
            'stop.sh': stop_script,
            'status.sh': status_script
        }
        
        for script_name, script_content in scripts.items():
            script_path = os.path.join(self.project_dir, script_name)
            with open(script_path, 'w') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)
            print(f"✅ Created: {script_path}")
    
    def create_requirements_check(self):
        """Create script to check if requirements are installed"""
        print("📋 Creating requirements checker...")
        
        check_script = f'''#!/bin/bash
# Check if requirements are installed in virtual environment

echo "🔍 Checking Python requirements..."

# Activate virtual environment
source {self.venv_path}/bin/activate

# Check if key packages are installed
python3 -c "
import sys
required_packages = [
    'flask', 'flask_cors', 'requests', 'pandas', 
    'numpy', 'talib', 'plotly', 'binance', 
    'python-dotenv', 'psutil'
]

missing_packages = []
for package in required_packages:
    try:
        __import__(package.replace('-', '_'))
        print(f'✅ {{package}}')
    except ImportError:
        missing_packages.append(package)
        print(f'❌ {{package}} - NOT INSTALLED')

if missing_packages:
    print(f'\\n⚠️ Missing packages: {{missing_packages}}')
    print('\\n📦 To install missing packages:')
    print(f'source {self.venv_path}/bin/activate')
    print(f'pip install {{\" \".join(missing_packages)}}')
    sys.exit(1)
else:
    print('\\n✅ All required packages are installed!')
    sys.exit(0)
"
'''
        
        check_file = os.path.join(self.project_dir, 'check_requirements.sh')
        with open(check_file, 'w') as f:
            f.write(check_script)
        os.chmod(check_file, 0o755)
        
        print(f"✅ Requirements checker created: {check_file}")
    
    def display_deployment_info(self):
        """Display deployment information"""
        print("\n" + "="*70)
        print("🎉 APACHE + WSGI DEPLOYMENT COMPLETED!")
        print("="*70)
        
        print(f"🌐 **Access URLs:**")
        print(f"   • Primary: http://{self.public_ip}")
        print(f"   • Local: http://{self.local_ip}")
        print(f"   • Localhost: http://localhost")
        
        print(f"\n📁 **Project Info:**")
        print(f"   • Project Directory: {self.project_dir}")
        print(f"   • Virtual Environment: {self.venv_path}")
        print(f"   • Python Path: {self.python_path}")
        print(f"   • WSGI File: {self.project_dir}/app.wsgi")
        
        print(f"\n🔧 **Management Commands:**")
        print(f"   • Start services: ./start.sh")
        print(f"   • Stop services: ./stop.sh")
        print(f"   • Check status: ./status.sh")
        print(f"   • Check requirements: ./check_requirements.sh")
        
        print(f"\n📊 **Apache Commands:**")
        print(f"   • Restart Apache: sudo systemctl restart apache2")
        print(f"   • Check Apache status: sudo systemctl status apache2")
        print(f"   • View Apache logs: sudo tail -f /var/log/apache2/{self.project_name}_error.log")
        print(f"   • View access logs: sudo tail -f /var/log/apache2/{self.project_name}_access.log")
        
        print(f"\n👥 **Supervisor Commands:**")
        print(f"   • Check worker status: sudo supervisorctl status")
        print(f"   • Restart worker: sudo supervisorctl restart {self.project_name}-worker")
        print(f"   • View worker logs: sudo tail -f /var/log/{self.project_name}-worker.log")
        
        print(f"\n📦 **Next Steps:**")
        print(f"   1. Install Python requirements:")
        print(f"      source {self.venv_path}/bin/activate")
        print(f"      pip install -r requirements.txt")
        print(f"   2. Configure .env file with your credentials")
        print(f"   3. Run: ./check_requirements.sh")
        print(f"   4. Run: ./start.sh")
        print(f"   5. Access: http://{self.public_ip}")
        
        print(f"\n⚠️ **Important Notes:**")
        print(f"   • Application runs under www-data user")
        print(f"   • Apache serves the application on port 80")
        print(f"   • Supervisor manages background workers")
        print(f"   • Firewall configured for HTTP/HTTPS access")
        print(f"   • Virtual environment isolated from system Python")
        
        print("="*70)
    
    def run_deployment(self):
        """Run complete deployment process"""
        print("🚀 Starting Ubuntu Apache + WSGI Deployment")
        print(f"📍 System: {platform.system()}")
        print(f"🌐 Public IP: {self.public_ip}")
        print(f"🏠 Local IP: {self.local_ip}")
        print(f"👤 User: {self.user}")
        print(f"📁 Project: {self.project_dir}")
        print("-" * 70)
        
        try:
            # Check root privileges
            self.check_root_privileges()
            
            # Step 1: Install system packages
            self.install_system_packages()
            
            # Step 2: Create virtual environment
            self.create_virtual_environment()
            
            # Step 3: Create WSGI file
            self.create_wsgi_file()
            
            # Step 4: Configure Apache
            self.configure_apache()
            
            # Step 5: Create Supervisor config
            self.create_supervisor_config()
            
            # Step 6: Setup firewall
            self.setup_firewall()
            
            # Step 7: Create management scripts
            self.create_startup_script()
            
            # Step 8: Create requirements checker
            self.create_requirements_check()
            
            # Step 9: Display information
            self.display_deployment_info()
            
            return True
            
        except Exception as e:
            print(f"❌ Deployment failed: {str(e)}")
            return False

def main():
    """Main function"""
    print("🔧 Crypto Backtest Signal - Ubuntu Apache + WSGI Deployment")
    print("=" * 60)
    
    # Check if running on Ubuntu
    if not os.path.exists('/etc/ubuntu-release') and 'ubuntu' not in platform.platform().lower():
        print("⚠️ This script is designed for Ubuntu systems")
        response = input("Continue anyway? (y/n): ").lower().strip()
        if response not in ['y', 'yes']:
            print("Deployment cancelled")
            sys.exit(1)
    
    # Run deployment
    deployer = UbuntuApacheDeployment()
    success = deployer.run_deployment()
    
    if success:
        print("\n✅ Deployment completed successfully!")
        print("\n📦 Next steps:")
        print("1. Install Python requirements: source venv/bin/activate && pip install -r requirements.txt")
        print("2. Configure .env file")
        print("3. Run: ./check_requirements.sh")
        print("4. Run: ./start.sh")
        print(f"5. Access: http://{deployer.public_ip}")
    else:
        print("\n❌ Deployment failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()