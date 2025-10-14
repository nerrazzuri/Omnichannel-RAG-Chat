"""
Quick script to update OpenAI API key.
"""
import os
from pathlib import Path

print("=" * 60)
print("OpenAI API Key Update")
print("=" * 60)

print("\n⚠️  IMPORTANT: OpenAI API keys should:")
print("  • Start with 'sk-' (usually 'sk-proj-')")
print("  • Be about 51-56 characters long")
print("  • NOT contain spaces or line breaks")

print("\nYour current key in .env is 164 characters - this is INVALID!")
print("A valid key looks like: sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

print("\n" + "-" * 60)
print("\nPlease get your API key from:")
print("https://platform.openai.com/api-keys")

print("\nPaste your VALID OpenAI API key below:")
print("(Make sure to copy the ENTIRE key, but nothing extra)")

api_key = input("API Key: ").strip()

# Validate
if not api_key:
    print("❌ No key entered!")
    exit(1)

print(f"\n📊 Key Analysis:")
print(f"  Length: {len(api_key)} characters")
print(f"  Starts with: {api_key[:10]}...")
print(f"  Ends with: ...{api_key[-4:]}")

if not api_key.startswith("sk-"):
    print("\n⚠️  WARNING: Key doesn't start with 'sk-'. This may not be valid.")
    confirm = input("Continue anyway? (y/n): ")
    if confirm.lower() != 'y':
        exit(1)

# Update .env file
env_file = Path(__file__).parent / ".env"

# Read existing content
if env_file.exists():
    with open(env_file, 'r') as f:
        lines = f.readlines()
else:
    lines = []

# Update or add OPENAI_API_KEY
updated = False
for i, line in enumerate(lines):
    if line.strip().startswith('OPENAI_API_KEY='):
        lines[i] = f'OPENAI_API_KEY={api_key}\n'
        updated = True
        break

if not updated:
    # Add at the beginning if not found
    lines.insert(0, f'# OpenAI Configuration\nOPENAI_API_KEY={api_key}\n\n')

# Write back
with open(env_file, 'w') as f:
    f.writelines(lines)

print(f"\n✅ API key updated in {env_file}")

# Test the key
print("\n🔄 Testing the key...")
try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    
    # Quick test
    models = client.models.list()
    print("✅ Successfully connected to OpenAI!")
    
    # Test embedding
    test_resp = client.embeddings.create(
        model="text-embedding-3-small",
        input="test"
    )
    print("✅ Embedding model works!")
    
    print("\n🎉 SUCCESS! Your API key is valid and working.")
    print("\n📌 Next steps:")
    print("1. Restart your backend server")
    print("2. Try uploading a file again")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\nThe key seems invalid. Please:")
    print("1. Check you copied the complete key")
    print("2. Make sure the key is active in your OpenAI account")
    print("3. Verify you have billing set up in OpenAI")