from typing import Dict, Any, List

from ai_core.pipeline.llm.llm_client import LLMClient


class ResponseFormatter:
    def __init__(self) -> None:
        self._llm = LLMClient()

    def generate(self, query: str, contexts: List[str], intent: str = "lookup", result_hint: str | None = None, tenant_id: str | None = None) -> Dict[str, Any]:
        """Use the same prompt and LLM call style as rag_service to assemble final payload.

        For now, delegate to rag_service prompt template and OpenAI client to keep parity.
        """
        if not contexts:
            return {
                "response": "I don’t have that information in the current database.",
                "citations": [],
                "confidence": 0.0,
                "requiresHuman": True,
            }
        gen = self._llm.generate(query, contexts, intent=intent, result_hint=result_hint, tenant_id=tenant_id)
        generated_text = (gen.get("text") or "").strip() or (contexts[0][:300] if contexts else "")
        # Citations: mirror rag_service best-effort from contexts
        citations: List[Dict[str, Any]] = []
        for i, ctx in enumerate(contexts[:6]):
            citations.append({
                "source": f"chunk_{i}",
                "title": f"Context {i+1}",
                "relevance": 0.8,
                "snippet": ctx[:160],
            })
        payload = {
            "response": generated_text,
            "citations": citations,
            "confidence": 0.0,
            "requiresHuman": False if contexts else True,
        }
        # Post-generation QC: if response is overly similar to raw context, reduce duplication by hinting stricter summary next pass (one retry)
        try:
            import difflib
            joined = "\n".join(contexts[:3])
            ratio = difflib.SequenceMatcher(a=generated_text.lower(), b=joined.lower()).ratio()
            if ratio > 0.9 and intent in ("summary", "lookup"):
                gen2 = self._llm.generate(query, contexts, intent="summary", result_hint=result_hint, tenant_id=tenant_id)
                txt2 = (gen2.get("text") or "").strip()
                if txt2 and len(txt2) < len(generated_text):
                    payload["response"] = txt2
        except Exception:
            pass
        return payload


