import os

from .base import env_bool


QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
OPENROUTER_APP_URL = os.getenv("OPENROUTER_APP_URL", "")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "newsletter-maker")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_TRUST_REMOTE_CODE = env_bool("EMBEDDING_TRUST_REMOTE_CODE", default=False)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
