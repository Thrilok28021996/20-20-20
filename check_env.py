#!/usr/bin/env python
"""
Environment variable checker for Railway deployment
"""
import os

required_vars = [
    'SECRET_KEY',
    'DATABASE_URL',
    'ALLOWED_HOSTS',
]

optional_vars = [
    'DEBUG',
    'REDIS_URL',
    'EMAIL_HOST_USER',
    'EMAIL_HOST_PASSWORD',
]

print("🔍 Checking environment variables...")

missing_required = []
for var in required_vars:
    value = os.environ.get(var)
    if not value:
        missing_required.append(var)
        print(f"❌ {var}: Missing")
    else:
        # Mask sensitive values
        if 'SECRET' in var or 'PASSWORD' in var:
            masked_value = f"{value[:8]}..." if len(value) > 8 else "***"
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"✅ {var}: {value}")

print("\n📋 Optional variables:")
for var in optional_vars:
    value = os.environ.get(var)
    if value:
        if 'SECRET' in var or 'PASSWORD' in var:
            masked_value = f"{value[:8]}..." if len(value) > 8 else "***"
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"✅ {var}: {value}")
    else:
        print(f"⚠️  {var}: Not set (optional)")

if missing_required:
    print(f"\n❌ Missing required environment variables: {', '.join(missing_required)}")
    print("\n📝 Add these variables in your Railway dashboard:")
    for var in missing_required:
        print(f"   {var}=your-value-here")
    exit(1)
else:
    print("\n🎉 All required environment variables are set!")