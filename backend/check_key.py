"""
Quick check of API key format
"""
import os
from pathlib import Path

# Load from .env
from dotenv import load_dotenv
env_file = Path(__file__).parent / ".env"
load_dotenv(env_file)

key = os.getenv("OPENAI_API_KEY", "")

print("=" * 60)
print("API Key Status Check")
print("=" * 60)

if not key:
    print("❌ No API key found in environment!")
else:
    print(f"📏 Length: {len(key)} characters")
    print(f"🔤 Starts with: {key[:10]}...")
    print(f"🔤 Ends with: ...{key[-4:]}")
    
    if len(key) > 60:
        print("\n❌ KEY IS TOO LONG!")
        print("   OpenAI keys are ~51-56 characters")
        print("   Your key appears to be corrupted or has extra characters")
        print("\n🔧 TO FIX:")
        print("   1. Get a fresh key from https://platform.openai.com/api-keys")
        print("   2. Run: python update_key.py")
    elif len(key) < 40:
        print("\n❌ KEY IS TOO SHORT!")
        print("   Make sure you copied the entire key")
    elif not key.startswith("sk-"):
        print("\n⚠️  Key doesn't start with 'sk-'")
        print("   This doesn't look like a valid OpenAI key")
    else:
        print("\n✅ Key format looks correct!")
        print("   If you still get errors, the key might be:")
        print("   • Revoked or expired")
        print("   • From a different account")
        print("   • Missing billing setup")

print("=" * 60)