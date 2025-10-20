"""
Centralized tuning knobs for chunking and retrieval.

Adjust values here to control behavior without touching multiple files.
"""
from dataclasses import dataclass
import os


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


@dataclass(frozen=True)
class ChunkingConfig:
    # Mode: 'tokens' (preferred) or 'chars'
    mode: str = os.getenv("CHUNK_MODE", "tokens").lower()
    # Token-based targets (used when mode == 'tokens')
    target_tokens: int = _get_int("CHUNK_TARGET_TOKENS", 800)
    overlap_tokens: int = _get_int("CHUNK_OVERLAP_TOKENS", 120)
    min_tokens: int = _get_int("CHUNK_MIN_TOKENS", 120)
    # Approximate character target per chunk (used when tokenization isn’t available)
    target_chars: int = _get_int("CHUNK_TARGET_CHARS", 1400)
    # Number of sentence overlap between chunks
    sentence_overlap: int = _get_int("CHUNK_SENTENCE_OVERLAP", 2)
    # Minimum characters to accept; otherwise merge with neighbors
    min_chars: int = _get_int("CHUNK_MIN_CHARS", 300)


@dataclass(frozen=True)
class RetrievalConfig:
    # Max contexts from hybrid retrieval before augmentation
    hybrid_top_k: int = _get_int("RETR_HYBRID_TOP_K", 12)
    # Vector augmentation hits
    vector_top_k: int = _get_int("RETR_VECTOR_TOP_K", 8)
    # Reranker cap and output size
    rerank_input_cap: int = _get_int("RETR_RERANK_INPUT_CAP", 30)
    rerank_top_k: int = _get_int("RETR_RERANK_TOP_K", 12)
    # Iterative expansion tries
    expand_variants: int = _get_int("RETR_EXPAND_VARIANTS", 4)
    # Enable/disable rule-based handlers (prefer AI-only when false)
    rules_enabled: bool = os.getenv("RETR_RULES_ENABLED", "false").lower() in ("1", "true", "yes")


# Singleton-style accessors
chunking = ChunkingConfig()
retrieval = RetrievalConfig()


