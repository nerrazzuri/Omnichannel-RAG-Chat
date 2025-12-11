"""
Debug script to verify Dynamic System Prompts (G.1) implementation.

This script tests that:
1. Tenant settings can store a custom system_prompt
2. RAGPipeline retrieves the system_prompt from tenant settings
3. LLMClient uses the custom system_prompt instead of the default
4. Different personas produce different response styles
"""

import sys
import os
from pathlib import Path

# Add backend/src to path - handle both running from root and from backend
script_dir = Path(__file__).parent.absolute()
backend_src = script_dir / "backend" / "src"

if not backend_src.exists():
    # Maybe we're already in backend
    backend_src = script_dir / "src"
    
if backend_src.exists():
    sys.path.insert(0, str(backend_src))
else:
    print(f"ERROR: Could not find backend/src directory")
    print(f"Script dir: {script_dir}")
    print(f"Tried: {script_dir / 'backend' / 'src'}")
    sys.exit(1)

print(f"✓ Added to path: {backend_src}")


from shared.database.session import get_db
from shared.database.models import Tenant
from ai_core.pipeline.rag_pipeline import RAGPipeline
import uuid


def test_default_system_prompt():
    """Test 1: Verify default behavior (no custom system prompt)"""
    print("\n" + "=" * 80)
    print("TEST 1: Default System Prompt")
    print("=" * 80)
    
    db = next(get_db())
    try:
        # Find or create a test tenant without custom system prompt
        tenant = db.query(Tenant).filter(Tenant.domain == "test-default.local").first()
        if not tenant:
            tenant = Tenant(
                id=str(uuid.uuid4()),
                name="Test Default Tenant",
                domain="test-default.local",
                settings={}  # No custom system_prompt
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        
        print(f"✓ Tenant: {tenant.name} ({tenant.id})")
        print(f"✓ Settings: {tenant.settings}")
        
        # Test RAG pipeline
        pipeline = RAGPipeline()
        query = "What is the refund policy?"
        
        print(f"\n📝 Query: {query}")
        print("⏳ Processing...")
        
        result = pipeline.answer(
            query=query,
            tenant_id=tenant.id,
            db=db,
            user_id="test-user",
            channel="web"
        )
        
        print(f"\n✅ Response: {result.get('response', 'N/A')[:200]}...")
        print(f"✅ Confidence: {result.get('confidence', 0.0)}")
        
    finally:
        db.close()


def test_pirate_persona():
    """Test 2: Verify custom system prompt (Pirate persona)"""
    print("\n" + "=" * 80)
    print("TEST 2: Custom System Prompt - Pirate Persona")
    print("=" * 80)
    
    db = next(get_db())
    try:
        # Find or create a test tenant with pirate persona
        tenant = db.query(Tenant).filter(Tenant.domain == "test-pirate.local").first()
        
        pirate_prompt = (
            "You are Captain Omni, a helpful pirate assistant. "
            "Speak like a pirate (use 'arr', 'matey', 'ye') while providing accurate information. "
            "Answer based only on provided context. If the answer is unknown, say so in pirate speak. "
            "Use [S#] tags to cite snippets after facts."
        )
        
        if not tenant:
            tenant = Tenant(
                id=str(uuid.uuid4()),
                name="Test Pirate Tenant",
                domain="test-pirate.local",
                settings={"system_prompt": pirate_prompt}
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        else:
            # Update settings if tenant exists
            tenant.settings = {"system_prompt": pirate_prompt}
            db.commit()
            db.refresh(tenant)
        
        print(f"✓ Tenant: {tenant.name} ({tenant.id})")
        print(f"✓ Custom Prompt: {pirate_prompt}")
        
        # Test RAG pipeline
        pipeline = RAGPipeline()
        query = "What is the refund policy?"
        
        print(f"\n📝 Query: {query}")
        print("⏳ Processing...")
        
        result = pipeline.answer(
            query=query,
            tenant_id=tenant.id,
            db=db,
            user_id="test-user",
            channel="web"
        )
        
        print(f"\n✅ Response: {result.get('response', 'N/A')}")
        print(f"✅ Confidence: {result.get('confidence', 0.0)}")
        
        # Check if response contains pirate language
        response_text = result.get('response', '').lower()
        pirate_words = ['arr', 'matey', 'ye', 'ahoy', 'aye']
        found_pirate = any(word in response_text for word in pirate_words)
        
        if found_pirate:
            print("\n🏴‍☠️ SUCCESS: Pirate language detected in response!")
        else:
            print("\n⚠️  WARNING: No pirate language detected. Check if custom prompt is being used.")
        
    finally:
        db.close()


def test_formal_persona():
    """Test 3: Verify custom system prompt (Formal business persona)"""
    print("\n" + "=" * 80)
    print("TEST 3: Custom System Prompt - Formal Business Persona")
    print("=" * 80)
    
    db = next(get_db())
    try:
        # Find or create a test tenant with formal persona
        tenant = db.query(Tenant).filter(Tenant.domain == "test-formal.local").first()
        
        formal_prompt = (
            "You are Omni Executive Assistant, a highly professional enterprise AI. "
            "Use formal business language, avoid contractions, and maintain a corporate tone. "
            "Begin responses with 'Dear User,' and end with 'Best regards, Omni'. "
            "Answer based only on provided context. Use [S#] tags to cite snippets."
        )
        
        if not tenant:
            tenant = Tenant(
                id=str(uuid.uuid4()),
                name="Test Formal Tenant",
                domain="test-formal.local",
                settings={"system_prompt": formal_prompt}
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        else:
            # Update settings if tenant exists
            tenant.settings = {"system_prompt": formal_prompt}
            db.commit()
            db.refresh(tenant)
        
        print(f"✓ Tenant: {tenant.name} ({tenant.id})")
        print(f"✓ Custom Prompt: {formal_prompt}")
        
        # Test RAG pipeline
        pipeline = RAGPipeline()
        query = "What is the refund policy?"
        
        print(f"\n📝 Query: {query}")
        print("⏳ Processing...")
        
        result = pipeline.answer(
            query=query,
            tenant_id=tenant.id,
            db=db,
            user_id="test-user",
            channel="web"
        )
        
        print(f"\n✅ Response: {result.get('response', 'N/A')}")
        print(f"✅ Confidence: {result.get('confidence', 0.0)}")
        
        # Check if response contains formal language
        response_text = result.get('response', '')
        formal_indicators = ['Dear User', 'Best regards', 'Omni']
        found_formal = any(indicator in response_text for indicator in formal_indicators)
        
        if found_formal:
            print("\n💼 SUCCESS: Formal business language detected in response!")
        else:
            print("\n⚠️  WARNING: No formal language detected. Check if custom prompt is being used.")
        
    finally:
        db.close()


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("DYNAMIC SYSTEM PROMPTS VERIFICATION")
    print("Testing G.1: Configurable persona prompts per tenant")
    print("=" * 80)
    
    try:
        # Test 1: Default behavior
        test_default_system_prompt()
        
        # Test 2: Pirate persona
        test_pirate_persona()
        
        # Test 3: Formal persona
        test_formal_persona()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 80)
        print("\nNOTE: Review the responses above to verify that:")
        print("1. Default tenant uses standard Omni assistant tone")
        print("2. Pirate tenant uses pirate language (arr, matey, ye)")
        print("3. Formal tenant uses professional business language")
        print("\nIf personas are not reflected, check:")
        print("- Tenant settings are correctly stored in database")
        print("- RAGPipeline retrieves system_prompt from tenant.settings")
        print("- LLMClient receives and uses the system_prompt parameter")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
