#!/usr/bin/env python3
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

print("🚀 Crash-safe server starting...")
print(f"🔍 Python version: {sys.version}")
print(f"🔍 Current directory: {os.getcwd()}")

# Log all environment variables
print("🔍 Environment variables:")
for key, value in sorted(os.environ.items()):
    if 'SECRET' in key or 'PASSWORD' in key or 'TOKEN' in key:
        print(f"  {key}: ***HIDDEN***")
    else:
        print(f"  {key}: {value}")

# Check for PORT variable
port = os.environ.get('PORT')
if not port:
    print("❌ PORT environment variable not set!")
    print("🔍 Available environment keys:", list(os.environ.keys()))
    port = 8000
else:
    print(f"✅ PORT found: {port}")

try:
    port = int(port)
    print(f"✅ PORT converted to integer: {port}")
except ValueError as e:
    print(f"❌ PORT conversion failed: {e}")
    port = 8000

class CrashSafeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            html = f"""
            <html>
            <head><title>Railway Test</title></head>
            <body>
                <h1>🎉 Server is working!</h1>
                <p><strong>Time:</strong> {datetime.now()}</p>
                <p><strong>Port:</strong> {port}</p>
                <p><strong>Environment PORT:</strong> {os.environ.get('PORT', 'NOT SET')}</p>
                <h2>Environment Variables:</h2>
                <ul>
            """

            for key, value in sorted(os.environ.items()):
                if 'SECRET' in key or 'PASSWORD' in key or 'TOKEN' in key:
                    html += f"<li><strong>{key}:</strong> ***HIDDEN***</li>"
                else:
                    html += f"<li><strong>{key}:</strong> {value}</li>"

            html += """
                </ul>
            </body>
            </html>
            """

            self.wfile.write(html.encode())

        except Exception as e:
            print(f"❌ Handler error: {e}")
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"[{datetime.now()}] {format % args}")

def main():
    try:
        print(f"🌐 Attempting to bind to 0.0.0.0:{port}")
        server = HTTPServer(('0.0.0.0', port), CrashSafeHandler)
        print(f"✅ Server successfully bound to port {port}")
        print(f"🚀 Starting server...")
        server.serve_forever()
    except Exception as e:
        print(f"❌ Server failed: {e}")
        print(f"📊 Exception type: {type(e)}")
        import traceback
        traceback.print_exc()

        # Keep container alive for debugging
        print("💤 Keeping container alive for 300 seconds for debugging...")
        time.sleep(300)
        sys.exit(1)

if __name__ == '__main__':
    main()