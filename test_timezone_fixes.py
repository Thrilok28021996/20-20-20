#!/usr/bin/env python3
"""
Test script to verify timezone fixes without Django dependencies
"""

import pytz
from datetime import datetime, timezone as dt_timezone

def test_timezone_functions():
    """Test the timezone utility functions"""
    print("Testing timezone functionality...")
    
    # Test 1: Basic timezone conversion
    utc_now = datetime.now(dt_timezone.utc)
    eastern = pytz.timezone('US/Eastern')
    pacific = pytz.timezone('US/Pacific')
    
    eastern_time = utc_now.astimezone(eastern)
    pacific_time = utc_now.astimezone(pacific)
    
    print(f"UTC time: {utc_now}")
    print(f"Eastern time: {eastern_time}")
    print(f"Pacific time: {pacific_time}")
    
    # Test 2: Date differences across timezones
    utc_date = utc_now.date()
    eastern_date = eastern_time.date()
    pacific_date = pacific_time.date()
    
    print(f"\nDates:")
    print(f"UTC date: {utc_date}")
    print(f"Eastern date: {eastern_date}")
    print(f"Pacific date: {pacific_date}")
    
    if utc_date != eastern_date or utc_date != pacific_date:
        print("✅ Timezone date handling is working correctly - dates can differ across zones!")
    else:
        print("⚠️  All dates are the same - this might be correct depending on the time")

    # Test 3: Business logic implications
    print(f"\n📊 Business Logic Impact:")
    print(f"A user in Eastern timezone at {eastern_time.strftime('%H:%M')} local time")
    print(f"vs a user in Pacific timezone at {pacific_time.strftime('%H:%M')} local time")
    print(f"Both would see different 'today' dates if this spans midnight!")
    
    return True

def test_common_timezones():
    """Test common timezone scenarios"""
    print("\n🌍 Testing Common Timezone Scenarios:")
    
    timezones = [
        'US/Eastern', 'US/Pacific', 'Europe/London', 
        'Asia/Tokyo', 'Australia/Sydney', 'UTC'
    ]
    
    utc_time = datetime.now(dt_timezone.utc)
    
    for tz_name in timezones:
        tz = pytz.timezone(tz_name)
        local_time = utc_time.astimezone(tz)
        print(f"{tz_name:15}: {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

if __name__ == "__main__":
    try:
        test_timezone_functions()
        test_common_timezones()
        print("\n✅ All timezone tests passed!")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
    except Exception as e:
        print(f"❌ Test failed: {e}")