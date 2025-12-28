#!/usr/bin/env python3
"""
Deployment Verification Script
Checks if all required configurations are properly set
"""

import os
import sys
import json

def check_environment_variables():
    """Check if environment variables are set"""
    print("🔍 Checking Environment Variables...")
    
    required_vars = {
        'API_ID': 'Telegram API ID',
        'API_HASH': 'Telegram API Hash',
        'BOT_TOKEN': 'Bot Token from @BotFather',
        'MONGO_URI': 'MongoDB Connection URI',
        'OWNER_ID': 'Bot Owner Telegram ID'
    }
    
    optional_vars = {
        'MONGO_DB_NAME': 'MongoDB Database Name',
        'LOG_CHANNEL': 'Log Channel ID'
    }
    
    missing = []
    found = []
    
    for var, description in required_vars.items():
        if os.getenv(var):
            found.append(f"   ✅ {var}: Set")
        else:
            missing.append(f"   ❌ {var}: Not set ({description})")
    
    for var, description in optional_vars.items():
        if os.getenv(var):
            found.append(f"   ✅ {var}: Set (optional)")
        else:
            found.append(f"   ⚠️  {var}: Not set (optional - {description})")
    
    print("\n".join(found))
    
    if missing:
        print("\n❌ Missing Required Variables:")
        print("\n".join(missing))
        return False
    
    print("\n✅ All required environment variables are set!")
    return True

def check_config_file():
    """Check if config.json exists and is valid"""
    print("\n🔍 Checking Config File...")
    
    if not os.path.exists('config.json'):
        print("   ⚠️  config.json not found (will use environment variables)")
        return True
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        required_keys = ['api_id', 'api_hash', 'bot_token', 'mongo_uri', 'owner_id']
        missing_keys = [key for key in required_keys if not config.get(key)]
        
        if missing_keys:
            print(f"   ❌ Missing keys in config.json: {', '.join(missing_keys)}")
            return False
        
        print("   ✅ config.json is valid!")
        return True
    
    except json.JSONDecodeError:
        print("   ❌ config.json is not valid JSON!")
        return False
    except Exception as e:
        print(f"   ❌ Error reading config.json: {e}")
        return False

def check_dependencies():
    """Check if required Python packages are installed"""
    print("\n🔍 Checking Python Dependencies...")
    
    required_packages = [
        'telethon',
        'motor',
        'pymongo'
    ]
    
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}: Installed")
        except ImportError:
            missing.append(package)
            print(f"   ❌ {package}: Not installed")
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("\n💡 Install with: pip install -r requirements.txt")
        return False
    
    print("\n✅ All dependencies are installed!")
    return True

def check_docker():
    """Check if running in Docker"""
    print("\n🔍 Checking Docker Environment...")
    
    if os.path.exists('/.dockerenv'):
        print("   ✅ Running in Docker container")
        return True
    else:
        print("   ℹ️  Not running in Docker (local/Heroku deployment)")
        return True

def check_heroku():
    """Check if running on Heroku"""
    print("\n🔍 Checking Heroku Environment...")
    
    if os.getenv('DYNO'):
        print("   ✅ Running on Heroku")
        print(f"   📦 Dyno: {os.getenv('DYNO')}")
        return True
    else:
        print("   ℹ️  Not running on Heroku")
        return True

def main():
    """Main verification function"""
    print("="*60)
    print("🤖 TELEGRAM AUTO FORWARD BOT")
    print("   Deployment Verification Script")
    print("="*60)
    print("\n✨ Created by: @AkMovieVerse")
    print("🔗 GK: https://t.me/akmovieshubx\n")
    
    checks = [
        check_docker(),
        check_heroku(),
        check_dependencies(),
        check_config_file(),
        check_environment_variables()
    ]
    
    print("\n" + "="*60)
    
    if all(checks):
        print("✅ ALL CHECKS PASSED!")
        print("="*60)
        print("\n💡 You can now start the bot with:")
        print("   python main.py start")
        print("\n" + "="*60 + "\n")
        return 0
    else:
        print("❌ SOME CHECKS FAILED!")
        print("="*60)
        print("\n💡 Please fix the issues above and try again.")
        print("\n📖 Deployment Guide: DEPLOYMENT.md")
        print("📖 Quick Start: QUICKSTART.md")
        print("\n" + "="*60 + "\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())

