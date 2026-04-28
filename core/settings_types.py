from typing import Protocol


class CoreSettings(Protocol):
    QDRANT_URL: str
    EMBEDDING_MODEL: str
    EMBEDDING_PROVIDER: str
    EMBEDDING_TRUST_REMOTE_CODE: bool
    OLLAMA_URL: str
    OPENROUTER_API_KEY: str
    OPENROUTER_API_BASE: str
    OPENROUTER_APP_URL: str
    OPENROUTER_APP_NAME: str
