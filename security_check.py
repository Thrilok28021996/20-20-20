#!/usr/bin/env python
"""
Security audit script for Django 20-20-20 application
"""
import os
import sys
import re
from pathlib import Path

def check_settings_security():
    """Check settings.py for security issues"""
    print("🔍 Checking settings.py security...")
    
    settings_path = Path('mysite/settings.py')
    if not settings_path.exists():
        print("❌ settings.py not found")
        return False
    
    content = settings_path.read_text()
    issues = []
    
    # Check for hard-coded secrets
    if 'django-insecure' in content and 'config(' not in content:
        issues.append("Hard-coded SECRET_KEY found")
    
    # Check DEBUG setting
    if 'DEBUG = True' in content and 'config(' not in content:
        issues.append("DEBUG hardcoded to True")
    
    # Check ALLOWED_HOSTS
    if 'ALLOWED_HOSTS = []' in content:
        issues.append("Empty ALLOWED_HOSTS")
    
    # Check security headers
    required_security_settings = [
        'SECURE_SSL_REDIRECT',
        'SESSION_COOKIE_SECURE',
        'CSRF_COOKIE_SECURE',
        'SECURE_BROWSER_XSS_FILTER',
        'SECURE_CONTENT_TYPE_NOSNIFF'
    ]
    
    for setting in required_security_settings:
        if setting not in content:
            issues.append(f"Missing {setting} setting")
    
    if issues:
        print("❌ Settings security issues:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("✅ Settings security looks good")
        return True

def check_csrf_exemptions():
    """Check for @csrf_exempt decorators"""
    print("🔍 Checking for CSRF exemptions...")
    
    csrf_exempt_files = []
    for root, dirs, files in os.walk('.'):
        # Skip migrations and __pycache__
        if 'migrations' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = Path(root) / file
                try:
                    content = filepath.read_text()
                    if '@csrf_exempt' in content:
                        csrf_exempt_files.append(str(filepath))
                except:
                    continue
    
    # Check if files contain legitimate webhook endpoints
    legitimate_exempt_files = []
    non_webhook_files = []
    
    for file in csrf_exempt_files:
        try:
            content = Path(file).read_text()
            if ('webhook' in content.lower() and 'stripe' in content.lower()) or \
               ('ipn' in content.lower() and 'paypal' in content.lower()) or \
               'security_check.py' in file:  # Ignore the security check script itself
                legitimate_exempt_files.append(file)
            else:
                non_webhook_files.append(file)
        except:
            non_webhook_files.append(file)
    
    if non_webhook_files:
        print("❌ CSRF exempt decorators found (non-webhook):")
        for file in non_webhook_files:
            print(f"   - {file}")
        return False
    elif legitimate_exempt_files:
        print("✅ CSRF exempt decorators found (legitimate webhooks only):")
        for file in legitimate_exempt_files:
            print(f"   - {file}")
        return True
    else:
        print("✅ No inappropriate CSRF exemptions found")
        return True

def check_env_file():
    """Check for .env file and sensitive data"""
    print("🔍 Checking .env configuration...")
    
    env_path = Path('.env')
    if not env_path.exists():
        print("❌ .env file not found")
        return False
    
    content = env_path.read_text()
    required_vars = [
        'SECRET_KEY',
        'STRIPE_SECRET_KEY',
        'EMAIL_HOST_PASSWORD',
        'ALLOWED_HOSTS'
    ]
    
    missing_vars = []
    for var in required_vars:
        if var not in content:
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    else:
        print("✅ .env file looks good")
        return True

def check_input_validation():
    """Check for input validation in views"""
    print("🔍 Checking input validation...")
    
    validation_found = False
    for root, dirs, files in os.walk('.'):
        if 'migrations' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if file == 'views.py':
                filepath = Path(root) / file
                try:
                    content = filepath.read_text()
                    if 'bleach.clean' in content or 'validate_and_sanitize' in content:
                        validation_found = True
                        print(f"✅ Input validation found in {filepath}")
                except:
                    continue
    
    if not validation_found:
        print("❌ No input validation found in views")
        return False
    
    return True

def check_sql_injection():
    """Check for potential SQL injection vulnerabilities"""
    print("🔍 Checking for SQL injection risks...")
    
    dangerous_patterns = [
        r'\.raw\s*\(',
        r'\.extra\s*\(',
        r'cursor\.execute\s*\([^%]',  # Raw SQL without parameterization
    ]
    
    issues = []
    for root, dirs, files in os.walk('.'):
        if 'migrations' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = Path(root) / file
                try:
                    content = filepath.read_text()
                    for pattern in dangerous_patterns:
                        if re.search(pattern, content):
                            issues.append(f"Potential SQL injection in {filepath}")
                except:
                    continue
    
    if issues:
        print("❌ Potential SQL injection risks:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("✅ No SQL injection risks found")
        return True

def check_security_middleware():
    """Check if security middleware is properly configured"""
    print("🔍 Checking security middleware...")
    
    settings_path = Path('mysite/settings.py')
    if not settings_path.exists():
        return False
    
    content = settings_path.read_text()
    
    required_middleware = [
        'django.middleware.security.SecurityMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'axes.middleware.AxesMiddleware',
        'csp.middleware.CSPMiddleware'
    ]
    
    missing_middleware = []
    for middleware in required_middleware:
        if middleware not in content:
            missing_middleware.append(middleware)
    
    if missing_middleware:
        print("❌ Missing security middleware:")
        for middleware in missing_middleware:
            print(f"   - {middleware}")
        return False
    else:
        print("✅ Security middleware properly configured")
        return True

def check_logging_configuration():
    """Check if logging is properly configured"""
    print("🔍 Checking logging configuration...")
    
    settings_path = Path('mysite/settings.py')
    if not settings_path.exists():
        return False
    
    content = settings_path.read_text()
    
    if 'LOGGING = {' in content:
        print("✅ Logging configuration found")
        return True
    else:
        print("❌ No logging configuration found")
        return False

def main():
    """Run all security checks"""
    print("🚀 Starting security audit for Django 20-20-20 application\n")
    
    checks = [
        ("Settings Security", check_settings_security),
        ("Environment Variables", check_env_file),
        ("CSRF Protection", check_csrf_exemptions),
        ("Input Validation", check_input_validation),
        ("SQL Injection", check_sql_injection),
        ("Security Middleware", check_security_middleware),
        ("Logging Configuration", check_logging_configuration),
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, check_func in checks:
        print(f"\n{'='*50}")
        print(f"Running: {check_name}")
        print('='*50)
        
        if check_func():
            passed += 1
        
    print(f"\n{'='*50}")
    print("🏁 SECURITY AUDIT SUMMARY")
    print('='*50)
    print(f"Passed: {passed}/{total} checks")
    
    if passed == total:
        print("🎉 All security checks passed!")
        return 0
    else:
        print("⚠️  Some security issues need attention")
        return 1

if __name__ == '__main__':
    exit(main())