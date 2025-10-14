"""
Interactive script to set up and verify OpenAI API key.
"""
import os
import sys
from pathlib import Path
from getpass import getpass

def setup_api_key():
    """Interactive setup for OpenAI API key."""
    print("=" * 60)
    print("OpenAI API Key Setup for Omnichannel Chatbot")
    print("=" * 60)
    
    env_file = Path(__file__).parent / ".env"
    
    print("\n📌 Important Information:")
    print("1. Your OpenAI API key should start with 'sk-'")
    print("2. It should be around 51-56 characters long")
    print("3. You can find it at: https://platform.openai.com/api-keys")
    print("4. Make sure the key has permissions for embeddings and chat completions")
    
    print("\n" + "-" * 40)
    
    # Check current key
    current_key = os.getenv("OPENAI_API_KEY", "")
    if current_key:
        masked = current_key[:7] + "..." + current_key[-4:] if len(current_key) > 11 else "***"
        print(f"\n✓ Current API key found: {masked}")
        print(f"  Length: {len(current_key)} characters")
        
        # Validate format
        if not current_key.startswith("sk-"):
            print("  ⚠️ Warning: Key doesn't start with 'sk-'")
        
        change = input("\nDo you want to change the API key? (y/n): ").lower()
        if change != 'y':
            print("Keeping existing key.")
            return
    else:
        print("\n✗ No API key currently configured")
    
    # Get new key
    print("\n" + "-" * 40)
    print("Enter your OpenAI API key")
    print("(it will be hidden for security):")
    
    new_key = getpass("API Key: ").strip()
    
    # Validate the new key
    if not new_key:
        print("✗ No key entered. Exiting.")
        return
    
    if not new_key.startswith("sk-"):
        print("\n⚠️ Warning: The key doesn't start with 'sk-'")
        print("OpenAI API keys typically start with 'sk-proj-' or 'sk-'")
        confirm = input("Continue anyway? (y/n): ").lower()
        if confirm != 'y':
            print("Setup cancelled.")
            return
    
    print(f"\n📊 Key Statistics:")
    print(f"  • Length: {len(new_key)} characters")
    print(f"  • Starts with: {new_key[:7]}...")
    print(f"  • Ends with: ...{new_key[-4:]}")
    
    # Test the key
    print("\n🔄 Testing API key...")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=new_key)
        
        # Try to list models
        response = client.models.list()
        print("✓ Successfully connected to OpenAI API!")
        
        # Try embedding
        test_embedding = client.embeddings.create(
            model="text-embedding-3-small",
            input="test"
        )
        print("✓ Embedding model access confirmed!")
        
    except Exception as e:
        print(f"✗ Error testing API key: {e}")
        print("\n⚠️ The API key appears to be invalid or lacks permissions.")
        save_anyway = input("Save it anyway? (y/n): ").lower()
        if save_anyway != 'y':
            print("Setup cancelled.")
            return
    
    # Update .env file
    print("\n📝 Updating .env file...")
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Find and replace the OPENAI_API_KEY line
        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith('OPENAI_API_KEY='):
                lines[i] = f'OPENAI_API_KEY={new_key}\n'
                updated = True
                break
        
        if not updated:
            # Add the key if not found
            lines.insert(0, f'OPENAI_API_KEY={new_key}\n')
        
        with open(env_file, 'w') as f:
            f.writelines(lines)
    else:
        # Create new .env file
        with open(env_file, 'w') as f:
            f.write(f'# Environment configuration\n')
            f.write(f'OPENAI_API_KEY={new_key}\n')
            f.write(f'DATABASE_URL=postgresql://user:password@localhost:5432/chatbot_dev\n')
            f.write(f'REDIS_URL=redis://localhost:6379/0\n')
            f.write(f'QDRANT_URL=http://localhost:6333\n')
            f.write(f'JWT_SECRET=your-jwt-secret-key-minimum-32-characters-change-this\n')
            f.write(f'JWT_EXPIRES_MINUTES=60\n')
            f.write(f'LOG_LEVEL=INFO\n')
            f.write(f'DEBUG=true\n')
    
    print(f"✓ API key saved to: {env_file}")
    
    # Set in current environment
    os.environ['OPENAI_API_KEY'] = new_key
    print("✓ API key set in current environment")
    
    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("\nNext steps:")
    print("1. Restart your backend service to load the new key")
    print("2. Test file uploads and queries")
    print("3. Keep your .env file secure and never commit it to git")
    print("=" * 60)

if __name__ == "__main__":
    setup_api_key()