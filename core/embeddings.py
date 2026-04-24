from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from uuid import uuid4

from django.conf import settings
from django.utils.dateparse import parse_datetime
import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from core.models import Content


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    def get_embedding_dimension(self) -> int:
        return len(self.embed_text("dimension probe"))


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self.model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            trust_remote_code=settings.EMBEDDING_TRUST_REMOTE_CODE,
        )

    def embed_text(self, text: str) -> list[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def get_embedding_dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())


class OllamaEmbeddingProvider(EmbeddingProvider):
    def embed_text(self, text: str) -> list[float]:
        normalized_text = normalize_text(text)
        response = httpx.post(
            f"{settings.OLLAMA_URL.rstrip('/')}/api/embed",
            json={"model": settings.EMBEDDING_MODEL, "input": [normalized_text]},
            timeout=30.0,
        )
        if response.status_code == 404:
            legacy_response = httpx.post(
                f"{settings.OLLAMA_URL.rstrip('/')}/api/embeddings",
                json={"model": settings.EMBEDDING_MODEL, "prompt": normalized_text},
                timeout=30.0,
            )
            legacy_response.raise_for_status()
            return legacy_response.json()["embedding"]
        response.raise_for_status()
        return response.json()["embeddings"][0]


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    def embed_text(self, text: str) -> list[float]:
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY must be set when using the openrouter embedding provider.")
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        if settings.OPENROUTER_APP_URL:
            headers["HTTP-Referer"] = settings.OPENROUTER_APP_URL
        if settings.OPENROUTER_APP_NAME:
            headers["X-OpenRouter-Title"] = settings.OPENROUTER_APP_NAME
        response = httpx.post(
            f"{settings.OPENROUTER_API_BASE.rstrip('/')}/embeddings",
            headers=headers,
            json={
                "model": settings.EMBEDDING_MODEL,
                "input": normalize_text(text),
                "encoding_format": "float",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


def collection_name_for_tenant(tenant_id: int) -> str:
    return f"tenant_{tenant_id}_content"


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.QDRANT_URL, timeout=10.0)


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    provider_name = settings.EMBEDDING_PROVIDER
    if provider_name == "sentence-transformers":
        return SentenceTransformerEmbeddingProvider()
    if provider_name == "ollama":
        return OllamaEmbeddingProvider()
    if provider_name == "openrouter":
        return OpenRouterEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: {provider_name}")


def get_embedding_dimension() -> int:
    return get_embedding_provider().get_embedding_dimension()


def embed_text(text: str) -> list[float]:
    return get_embedding_provider().embed_text(normalize_text(text))


def upsert_content_embedding(content: Content) -> str:
    client = get_qdrant_client()
    ensure_tenant_collection(content.tenant_id)
    embedding_id = content.embedding_id or str(uuid4())
    vector = embed_text(build_content_embedding_text(content))
    client.upsert(
        collection_name=collection_name_for_tenant(content.tenant_id),
        points=[
            PointStruct(
                id=embedding_id,
                vector=vector,
                payload={
                    "content_id": content.id,
                    "tenant_id": content.tenant_id,
                    "url": content.url,
                    "title": content.title,
                    "published_date": serialize_published_date(content.published_date),
                    "source_plugin": content.source_plugin,
                    "is_reference": content.is_reference,
                },
            )
        ],
        wait=True,
    )
    if content.embedding_id != embedding_id:
        content.embedding_id = embedding_id
        content.save(update_fields=["embedding_id"])
    return embedding_id


def search_similar(
    tenant_id: int,
    query_vector: list[float],
    limit: int = 10,
    *,
    is_reference: bool | None = None,
    exclude_content_id: int | None = None,
):
    if not tenant_collection_exists(tenant_id):
        return []
    query_filter = build_search_filter(is_reference=is_reference, exclude_content_id=exclude_content_id)
    return get_qdrant_client().search(
        collection_name=collection_name_for_tenant(tenant_id),
        query_vector=query_vector,
        limit=limit,
        query_filter=query_filter,
        with_payload=True,
    )


def search_similar_content(content: Content, limit: int = 10, *, is_reference: bool | None = None):
    return search_similar(
        content.tenant_id,
        embed_text(build_content_embedding_text(content)),
        limit=limit,
        is_reference=is_reference,
        exclude_content_id=content.id,
    )


def get_reference_similarity(tenant_id: int, vector: list[float], limit: int = 5) -> float:
    scored_points = search_similar(tenant_id, vector, limit=limit, is_reference=True)
    if not scored_points:
        return 0.0
    return sum(point.score for point in scored_points) / len(scored_points)


def ensure_tenant_collection(tenant_id: int) -> None:
    client = get_qdrant_client()
    collection_name = collection_name_for_tenant(tenant_id)
    if tenant_collection_exists(tenant_id):
        return
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=get_embedding_dimension(), distance=Distance.COSINE),
    )


def tenant_collection_exists(tenant_id: int) -> bool:
    try:
        get_qdrant_client().get_collection(collection_name_for_tenant(tenant_id))
    except Exception:
        return False
    return True


def build_content_embedding_text(content: Content) -> str:
    return "\n\n".join(part for part in [content.title, content.content_text] if part)


def normalize_text(text: str) -> str:
    normalized_text = text.strip()
    if not normalized_text:
        return "empty content"
    return normalized_text


def serialize_published_date(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, str):
        parsed_value = parse_datetime(value)
        if parsed_value is not None:
            return parsed_value.isoformat()
        return value
    return str(value)


def build_search_filter(*, is_reference: bool | None = None, exclude_content_id: int | None = None):
    conditions = []
    if is_reference is not None:
        conditions.append(FieldCondition(key="is_reference", match=MatchValue(value=is_reference)))
    if exclude_content_id is not None:
        conditions.append(FieldCondition(key="content_id", match=MatchValue(value=exclude_content_id)))
    if not conditions:
        return None
    return Filter(must=conditions if exclude_content_id is None else conditions[:-1], must_not=conditions[-1:] if exclude_content_id is not None else None)