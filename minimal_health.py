#!/usr/bin/env python
"""
Minimal health check server for debugging Railway deployment
"""
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            response = {
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
                'service': 'minimal-health',
                'environment': dict(os.environ)
            }

            self.wfile.write(json.dumps(response, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def log_message(self, format, *args):
        # Override to reduce noise
        print(f"[{datetime.now()}] {format % args}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"Starting minimal health server on port {port}")

    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"Health check available at: http://0.0.0.0:{port}/health/")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down server...")
        server.shutdown()