"""
Start the backend service with proper configuration
"""
import os
import sys
from pathlib import Path

# Add src directory to Python path
backend_dir = Path(__file__).parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

# Load environment variables from .env
from dotenv import load_dotenv
env_file = backend_dir / ".env"
if env_file.exists():
    print(f"Loading environment from: {env_file}")
    load_dotenv(env_file, override=True)
    
    # Verify API key is loaded
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        print(f"✓ API Key loaded: {api_key[:15]}...{api_key[-4:]}")
        print(f"  Length: {len(api_key)} characters")
    else:
        print("⚠️  Warning: No API key found in environment!")
else:
    print(f"⚠️  Warning: .env file not found at {env_file}")

print("\nStarting AI Core backend service...")
print("=" * 50)

# Now import and run the main app
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "ai_core.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )