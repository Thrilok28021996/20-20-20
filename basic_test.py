#!/usr/bin/env python3
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response = {
            'status': 'Container is running!',
            'timestamp': datetime.now().isoformat(),
            'port': os.environ.get('PORT', 'not set'),
            'environment': dict(os.environ),
            'python_version': sys.version,
            'path': os.getcwd(),
            'files': os.listdir('.')
        }

        self.wfile.write(json.dumps(response, indent=2).encode())

    def log_message(self, format, *args):
        print(f"[{datetime.now()}] {format % args}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"🚀 Starting basic test server on port {port}")
    print(f"🔍 Environment PORT: {os.environ.get('PORT')}")
    print(f"🔍 Current directory: {os.getcwd()}")
    print(f"🔍 Python executable: {sys.executable}")

    try:
        server = HTTPServer(('0.0.0.0', port), TestHandler)
        print(f"✅ Server bound to 0.0.0.0:{port}")
        print(f"🌐 Server starting...")
        server.serve_forever()
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)