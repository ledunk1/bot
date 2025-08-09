#!/bin/bash
# Install Python requirements in virtual environment

echo "📦 Installing Python Requirements..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Run deploy_apache.py first to create virtual environment"
    exit 1
fi

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📦 Installing requirements from requirements.txt..."
pip install -r requirements.txt

# Install additional packages for production
echo "🚀 Installing production packages..."
pip install gunicorn gevent

# Verify installation
echo "✅ Verifying installation..."
python3 -c "
import flask, pandas, numpy, talib, plotly, binance
print('✅ Core packages installed successfully!')
print('Flask version:', flask.__version__)
print('Pandas version:', pandas.__version__)
print('NumPy version:', numpy.__version__)
"

echo ""
echo "✅ Requirements installation completed!"
echo "🔧 Run ./check_requirements.sh to verify all packages"
echo "🚀 Run ./start.sh to start the services"