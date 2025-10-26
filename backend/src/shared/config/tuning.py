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
    # Field-value vector hits
    field_value_top_k: int = _get_int("RETR_FIELD_VALUE_TOP_K", 8)
    # Reranker cap and output size
    rerank_input_cap: int = _get_int("RETR_RERANK_INPUT_CAP", 30)
    rerank_top_k: int = _get_int("RETR_RERANK_TOP_K", 12)
    # Iterative expansion tries
    expand_variants: int = _get_int("RETR_EXPAND_VARIANTS", 4)
    # Expansion cache TTL (seconds)
    expand_cache_ttl: int = _get_int("RETR_EXPAND_CACHE_TTL", 1800)
    # Enable/disable rule-based handlers (prefer AI-only when false)
    rules_enabled: bool = os.getenv("RETR_RULES_ENABLED", "false").lower() in ("1", "true", "yes")
    # Hybrid retrieval and weights
    hybrid_enabled: bool = os.getenv("RETR_HYBRID_ENABLED", "true").lower() in ("1", "true", "yes")
    expansion_enabled: bool = os.getenv("RETR_EXPANSION_ENABLED", "true").lower() in ("1", "true", "yes")
    hybrid_weight_vector: float = _get_float("RETR_HYBRID_WEIGHT_VECTOR", 0.7)
    hybrid_weight_bm25: float = _get_float("RETR_HYBRID_WEIGHT_BM25", 0.3)
    # Enable/disable individual retrievers
    hybrid_use_bm25: bool = os.getenv("RETR_USE_BM25", "true").lower() in ("1", "true", "yes")
    hybrid_use_dense: bool = os.getenv("RETR_USE_DENSE", "true").lower() in ("1", "true", "yes")
    # Tenant isolation/per-tenant collection
    per_tenant_collections: bool = os.getenv("RETR_PER_TENANT_COLLECTIONS", "false").lower() in ("1", "true", "yes")
    # RRF fusion parameters
    rrf_k: int = _get_int("RETR_RRF_K", 60)
    rrf_w_bm25: float = _get_float("RETR_RRF_W_BM25", 0.4)
    rrf_w_dense: float = _get_float("RETR_RRF_W_DENSE", 0.5)
    rrf_w_field_values: float = _get_float("RETR_RRF_W_FIELD_VALUES", 0.6)
    # Semantic-only fallback controls
    semantic_fallback_enabled: bool = os.getenv("RETR_SEMANTIC_FALLBACK_ENABLED", "true").lower() in ("1", "true", "yes")
    semantic_fallback_topk_multiplier: int = _get_int("RETR_SEMANTIC_FALLBACK_TOPK_MULT", 2)
    # Embedding and fine-tuning controls
    embedding_model: str = os.getenv("RAG_EMBED_MODEL", "text-embedding-3-large")
    fine_tune_enabled: bool = os.getenv("EMBED_FINE_TUNE_ENABLED", "false").lower() in ("1", "true", "yes")
    fine_tune_model_path: str = os.getenv("EMBED_FINE_TUNE_MODEL_PATH", "")

@dataclass(frozen=True)
class RerankerConfig:
    # CrossEncoder设置
    cross_encoder_model: str = os.getenv("RERANK_CROSS_ENCODER", "cross-encoder/ms-marco-electra-base")
    cross_encoder_batch_size: int = _get_int("RERANK_BATCH_SIZE", 16)
    cross_encoder_max_length: int = _get_int("RERANK_MAX_LENGTH", 512)
    
    # LTR设置
    ltr_model_path: str = os.getenv("RERANK_LTR_MODEL_PATH", "")
    ltr_enabled: bool = os.getenv("RERANK_LTR_ENABLED", "false").lower() in ("1", "true", "yes")
    
    # Enable/disable the reranker pipeline globally
    enabled: bool = os.getenv("RERANK_ENABLED", "true").lower() in ("1", "true", "yes")
    
    # 融合权重
    fusion_bi_weight: float = _get_float("RERANK_BI_WEIGHT", 0.3)
    fusion_cross_weight: float = _get_float("RERANK_CROSS_WEIGHT", 0.7)
    
    # 缓存设置
    cache_enabled: bool = os.getenv("RERANK_CACHE_ENABLED", "true").lower() in ("1", "true", "yes")
    cache_ttl: int = _get_int("RERANK_CACHE_TTL", 3600)
    # Schema bias factor applied to matching contexts
    schema_bias_factor: float = _get_float("RERANK_SCHEMA_BIAS_FACTOR", 1.1)
 
# Singleton-style accessors
chunking = ChunkingConfig()
retrieval = RetrievalConfig()
reranker_config = RerankerConfig()  # 新增的


