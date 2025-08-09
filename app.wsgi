#!/usr/bin/env python3
"""
WSGI Application Entry Point for Apache
"""
import sys
import os
from pathlib import Path

# Get project directory
project_dir = str(Path(__file__).parent.absolute())

# Add project directory to Python path
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Set environment variables
os.environ['PYTHONPATH'] = project_dir

# Change to project directory
os.chdir(project_dir)

# Import the production Flask application
try:
    from app_production import app as application
    print(f"✅ WSGI: Loaded production app from {project_dir}")
except ImportError as e:
    print(f"❌ WSGI: Failed to import production app: {str(e)}")
    # Fallback to regular app
    from app import app as application
    print(f"⚠️ WSGI: Using fallback app")

# Ensure application is callable
if not callable(application):
    raise RuntimeError("Application is not callable")

print(f"🚀 WSGI: Application ready for Apache")