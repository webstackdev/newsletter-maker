import os

from .base import env_bool


def env_float(name: str, default: float) -> float:
	value = os.getenv(name)
	if value is None:
		return default
	return float(value)


def env_int(name: str, default: int) -> int:
	value = os.getenv(name)
	if value is None:
		return default
	return int(value)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
OPENROUTER_APP_URL = os.getenv("OPENROUTER_APP_URL", "")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "newsletter-maker")
AI_CLASSIFICATION_MODEL = os.getenv("AI_CLASSIFICATION_MODEL", "meta-llama/llama-3.1-70b-instruct")
AI_RELEVANCE_MODEL = os.getenv("AI_RELEVANCE_MODEL", "qwen/qwen-2.5-72b-instruct")
AI_SUMMARIZATION_MODEL = os.getenv("AI_SUMMARIZATION_MODEL", "google/gemma-3-27b-it")
AI_CLASSIFICATION_REVIEW_THRESHOLD = env_float("AI_CLASSIFICATION_REVIEW_THRESHOLD", default=0.6)
AI_RELEVANCE_LOW_THRESHOLD = env_float("AI_RELEVANCE_LOW_THRESHOLD", default=0.5)
AI_RELEVANCE_HIGH_THRESHOLD = env_float("AI_RELEVANCE_HIGH_THRESHOLD", default=0.85)
AI_RELEVANCE_REVIEW_THRESHOLD = env_float("AI_RELEVANCE_REVIEW_THRESHOLD", default=0.4)
AI_RELEVANCE_SUMMARIZE_THRESHOLD = env_float("AI_RELEVANCE_SUMMARIZE_THRESHOLD", default=0.7)
AI_MAX_NODE_RETRIES = env_int("AI_MAX_NODE_RETRIES", default=2)
AI_REQUEST_TIMEOUT_SECONDS = env_float("AI_REQUEST_TIMEOUT_SECONDS", default=60.0)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_TRUST_REMOTE_CODE = env_bool("EMBEDDING_TRUST_REMOTE_CODE", default=False)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

__all__ = [
	"QDRANT_URL",
	"OPENROUTER_API_KEY",
	"OPENROUTER_API_BASE",
	"OPENROUTER_APP_URL",
	"OPENROUTER_APP_NAME",
	"AI_CLASSIFICATION_MODEL",
	"AI_RELEVANCE_MODEL",
	"AI_SUMMARIZATION_MODEL",
	"AI_CLASSIFICATION_REVIEW_THRESHOLD",
	"AI_RELEVANCE_LOW_THRESHOLD",
	"AI_RELEVANCE_HIGH_THRESHOLD",
	"AI_RELEVANCE_REVIEW_THRESHOLD",
	"AI_RELEVANCE_SUMMARIZE_THRESHOLD",
	"AI_MAX_NODE_RETRIES",
	"AI_REQUEST_TIMEOUT_SECONDS",
	"EMBEDDING_PROVIDER",
	"EMBEDDING_MODEL",
	"EMBEDDING_TRUST_REMOTE_CODE",
	"OLLAMA_URL",
]
