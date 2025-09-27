#!/bin/bash
set -e

echo "🚀 Minimal Railway test started at $(date)"
echo "🔍 PORT: ${PORT}"
echo "🔍 PWD: $(pwd)"
echo "🔍 Python version: $(python --version)"
echo "🔍 Files in directory:"
ls -la

# Test Django import
echo "🐍 Testing Django import..."
python -c "import django; print(f'Django version: {django.get_version()}')"

# Test settings
echo "⚙️ Testing settings..."
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
import django
django.setup()
print('✅ Django setup successful')
"

# Start simple HTTP server first
echo "🌐 Starting simple HTTP server on port ${PORT}..."
python -c "
import http.server
import socketserver
import os

PORT = int(os.environ.get('PORT', 8000))
Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(('', PORT), Handler) as httpd:
    print(f'Serving at port {PORT}')
    httpd.serve_forever()
"