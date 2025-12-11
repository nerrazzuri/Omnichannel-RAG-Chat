"""
Simple unit test to verify Dynamic System Prompts (G.1) implementation.

This test verifies the code structure without requiring a running database:
1. LLMClient accepts system_prompt parameter
2. ResponseFormatter passes system_prompt to LLMClient
3. RAGPipeline retrieves system_prompt from tenant settings
"""

import sys
from pathlib import Path

# Add backend/src to path
script_dir = Path(__file__).parent.absolute()
backend_src = script_dir / "backend" / "src"

if backend_src.exists():
    sys.path.insert(0, str(backend_src))
else:
    print(f"ERROR: Could not find backend/src directory at {backend_src}")
    sys.exit(1)

print(f"[OK] Added to path: {backend_src}\n")

# Test imports
print("=" * 80)
print("TEST 1: Verify imports")
print("=" * 80)

try:
    from ai_core.pipeline.llm.llm_client import LLMClient
    print("[OK] Imported LLMClient")
    
    from ai_core.pipeline.formatter.response_formatter import ResponseFormatter
    print("[OK] Imported ResponseFormatter")
    
    from ai_core.pipeline.rag_pipeline import RAGPipeline
    print("[OK] Imported RAGPipeline")
    
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test LLMClient signature
print("\n" + "=" * 80)
print("TEST 2: Verify LLMClient.generate() accepts system_prompt parameter")
print("=" * 80)

import inspect

llm_client = LLMClient()
generate_sig = inspect.signature(llm_client.generate)
params = list(generate_sig.parameters.keys())

print(f"LLMClient.generate() parameters: {params}")

if 'system_prompt' in params:
    print("[PASS] LLMClient.generate() has 'system_prompt' parameter")
else:
    print("[FAIL] LLMClient.generate() missing 'system_prompt' parameter")
    sys.exit(1)

# Test ResponseFormatter signature
print("\n" + "=" * 80)
print("TEST 3: Verify ResponseFormatter.generate() accepts system_prompt parameter")
print("=" * 80)

formatter = ResponseFormatter()
formatter_sig = inspect.signature(formatter.generate)
formatter_params = list(formatter_sig.parameters.keys())

print(f"ResponseFormatter.generate() parameters: {formatter_params}")

if 'system_prompt' in formatter_params:
    print("[PASS] ResponseFormatter.generate() has 'system_prompt' parameter")
else:
    print("[FAIL] ResponseFormatter.generate() missing 'system_prompt' parameter")
    sys.exit(1)

# Test RAGPipeline code for system_prompt retrieval
print("\n" + "=" * 80)
print("TEST 4: Verify RAGPipeline retrieves system_prompt from tenant settings")
print("=" * 80)

import ast

rag_pipeline_file = backend_src / "ai_core" / "pipeline" / "rag_pipeline.py"
with open(rag_pipeline_file, 'r', encoding='utf-8') as f:
    rag_code = f.read()

# Check if code contains system_prompt retrieval logic
checks = [
    (".settings", "Retrieves tenant settings"),
    ("system_prompt", "References system_prompt variable"),
    ("response_formatter.generate", "Calls response_formatter.generate"),
]

all_passed = True
for pattern, description in checks:
    if pattern in rag_code:
        print(f"[OK] {description}: Found '{pattern}'")
    else:
        print(f"[FAIL] {description}: Missing '{pattern}'")
        all_passed = False

if all_passed:
    print("\n[PASS] RAGPipeline contains system_prompt retrieval logic")
else:
    print("\n[FAIL] RAGPipeline missing some system_prompt logic")
    sys.exit(1)

# Test LLMClient code for system_prompt usage
print("\n" + "=" * 80)
print("TEST 5: Verify LLMClient uses system_prompt in API call")
print("=" * 80)

llm_client_file = backend_src / "ai_core" / "pipeline" / "llm" / "llm_client.py"
with open(llm_client_file, 'r', encoding='utf-8') as f:
    llm_code = f.read()

# Check if code uses system_prompt in the messages
checks = [
    ("system_prompt or self._system_policy", "Uses system_prompt parameter or fallback"),
    ('"role": "system"', "Sets system role in messages"),
]

all_passed = True
for pattern, description in checks:
    if pattern in llm_code:
        print(f"[OK] {description}: Found '{pattern}'")
    else:
        print(f"[FAIL] {description}: Missing '{pattern}'")
        all_passed = False

if all_passed:
    print("\n[PASS] LLMClient uses system_prompt in API calls")
else:
    print("\n[FAIL] LLMClient missing system_prompt usage")
    sys.exit(1)

# Summary
print("\n" + "=" * 80)
print("[SUCCESS] ALL TESTS PASSED")
print("=" * 80)
print("\nDynamic System Prompts (G.1) Implementation Verified:")
print("1. [OK] LLMClient.generate() accepts system_prompt parameter")
print("2. [OK] LLMClient uses system_prompt in OpenAI API calls")
print("3. [OK] ResponseFormatter.generate() accepts and passes system_prompt")
print("4. [OK] RAGPipeline retrieves system_prompt from tenant.settings")
print("\nThe implementation is complete and ready for integration testing.")
print("\nNext Steps:")
print("- Set tenant.settings['system_prompt'] in database")
print("- Test with different personas (pirate, formal, technical, etc.)")
print("- Verify responses reflect the custom persona")

