"""
Test the current API key from .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_file = Path(__file__).parent / ".env"
load_dotenv(env_file, override=True)  # Force override any existing env vars

key = os.getenv("OPENAI_API_KEY", "")

print("=" * 60)
print("Testing Current API Key from .env")
print("=" * 60)

print(f"\n📏 Key length: {len(key)} characters")
print(f"🔤 Starts with: {key[:15]}...")
print(f"🔤 Ends with: ...{key[-4:]}")

if len(key) != 164:
    print(f"\n⚠️  Key has been changed (was 164, now {len(key)})")
else:
    print("\n⚠️  This is still the 164-character key")

print("\n🔄 Testing with OpenAI API...")

try:
    from openai import OpenAI
    client = OpenAI(api_key=key)
    
    # Test the key
    response = client.models.list()
    models = [m.id for m in response.data[:3]]
    
    print("✅ SUCCESS! Key is valid!")
    print(f"   Available models: {', '.join(models)}")
    
    # Test embedding
    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input="test"
    )
    print(f"✅ Embedding works! Dimension: {len(emb.data[0].embedding)}")
    
except Exception as e:
    error_msg = str(e)
    if "401" in error_msg or "Incorrect API key" in error_msg:
        print(f"❌ API Key is INVALID!")
        print(f"   Error: {error_msg[:200]}")
        print("\n📝 This key doesn't work. You need a valid OpenAI API key.")
        print("   Valid keys are ~51-56 characters and start with 'sk-'")
    else:
        print(f"❌ Error: {error_msg[:200]}")

print("\n" + "=" * 60)