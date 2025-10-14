"""
Test script to verify OpenAI API key configuration.
"""
import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_api_key():
    """Test if the OpenAI API key is properly configured."""
    print("Testing OpenAI API Key Configuration...")
    print("=" * 50)
    
    # Test 1: Check environment variable
    print("\n1. Checking environment variable...")
    env_api_key = os.getenv("OPENAI_API_KEY")
    if env_api_key:
        # Mask the key for security
        masked_key = env_api_key[:15] + "..." + env_api_key[-4:]
        print(f"   ✓ OPENAI_API_KEY found in environment: {masked_key}")
    else:
        print("   ✗ OPENAI_API_KEY not found in environment")
    
    # Test 2: Check .env file
    print("\n2. Checking .env file...")
    env_file = backend_dir / ".env"
    if env_file.exists():
        print(f"   ✓ .env file found at: {env_file}")
        with open(env_file, 'r') as f:
            content = f.read()
            if 'OPENAI_API_KEY' in content:
                print("   ✓ OPENAI_API_KEY found in .env file")
            else:
                print("   ✗ OPENAI_API_KEY not found in .env file")
    else:
        print(f"   ✗ .env file not found at: {env_file}")
    
    # Test 3: Load configuration
    print("\n3. Loading configuration via settings...")
    try:
        from src.shared.config.settings import settings
        
        if settings.openai_api_key:
            masked_key = settings.openai_api_key[:15] + "..." + settings.openai_api_key[-4:]
            print(f"   ✓ API key loaded in settings: {masked_key}")
            print(f"   ✓ Key length: {len(settings.openai_api_key)} characters")
        else:
            print("   ✗ API key not loaded in settings")
    except Exception as e:
        print(f"   ✗ Error loading settings: {e}")
    
    # Test 4: Test OpenAI connection
    print("\n4. Testing OpenAI connection...")
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or settings.openai_api_key)
        
        # Try a simple API call
        response = client.models.list()
        available_models = [model.id for model in response.data[:5]]  # Get first 5 models
        
        print("   ✓ Successfully connected to OpenAI API")
        print(f"   ✓ Available models (first 5): {', '.join(available_models)}")
        
        # Test embedding model specifically
        test_text = "This is a test."
        embedding_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=test_text
        )
        
        if embedding_response.data:
            print("   ✓ Embedding model 'text-embedding-3-small' is working")
            print(f"   ✓ Embedding dimension: {len(embedding_response.data[0].embedding)}")
        
    except Exception as e:
        print(f"   ✗ Error connecting to OpenAI API: {e}")
        if "api_key" in str(e).lower():
            print("   ℹ Suggestion: Check if your API key is valid and has proper permissions")
        elif "rate" in str(e).lower():
            print("   ℹ Suggestion: You might have hit rate limits. This is actually a good sign - the key works!")
    
    print("\n" + "=" * 50)
    print("Test complete!")

if __name__ == "__main__":
    # Load environment variables from .env file
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded .env from: {env_path}\n")
    
    test_api_key()