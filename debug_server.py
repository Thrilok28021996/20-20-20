#!/usr/bin/env python3
import os
import sys
import time
import socket
from datetime import datetime

def log_debug(message):
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] {message}")

    # Also write to file for Railway logs
    try:
        with open('/app/debug.log', 'a') as f:
            f.write(f"[{timestamp}] {message}\n")
    except:
        pass

def test_port_binding(port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', port))
        sock.listen(1)
        log_debug(f"✅ Successfully bound to port {port}")

        # Accept one connection and respond
        log_debug(f"🌐 Listening on port {port}...")
        conn, addr = sock.accept()
        log_debug(f"📞 Connection from {addr}")

        response = b"""HTTP/1.1 200 OK\r
Content-Type: text/html\r
Content-Length: 200\r
\r
<html><body><h1>Railway Test Success!</h1><p>Server is running on port """ + str(port).encode() + b"""</p><p>Time: """ + datetime.now().isoformat().encode() + b"""</p></body></html>"""

        conn.send(response)
        conn.close()
        sock.close()

        log_debug(f"✅ Successfully handled request on port {port}")
        return True

    except Exception as e:
        log_debug(f"❌ Port {port} failed: {e}")
        return False

def main():
    log_debug("🚀 Debug server starting...")
    log_debug(f"🐍 Python: {sys.version}")
    log_debug(f"📁 CWD: {os.getcwd()}")
    log_debug(f"👤 User: {os.getuid() if hasattr(os, 'getuid') else 'unknown'}")

    # Log environment
    port_env = os.environ.get('PORT')
    log_debug(f"🔍 PORT env var: {port_env}")
    log_debug(f"🔍 Environment keys: {list(os.environ.keys())}")

    # Test different ports
    ports_to_try = []

    if port_env:
        try:
            ports_to_try.append(int(port_env))
        except:
            log_debug(f"❌ Could not convert PORT '{port_env}' to integer")

    ports_to_try.extend([8000, 3000, 5000, 8080])

    for port in ports_to_try:
        log_debug(f"🔧 Trying port {port}...")
        if test_port_binding(port):
            log_debug(f"🎉 Success on port {port}! Keeping server alive...")
            time.sleep(600)  # Keep alive for 10 minutes
            return

    log_debug("❌ All ports failed! Keeping container alive for debugging...")
    time.sleep(600)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log_debug(f"💥 Fatal error: {e}")
        import traceback
        log_debug(f"📊 Traceback: {traceback.format_exc()}")
        time.sleep(600)  # Keep alive even on fatal error