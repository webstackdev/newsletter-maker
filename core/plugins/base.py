"""Base types and shared behavior for ingestion source plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse


@dataclass(slots=True)
class ContentItem:
    """Normalized content payload returned by source plugins."""

    url: str
    title: str
    author: str
    published_date: datetime
    content_text: str
    source_plugin: str
    source_metadata: dict[str, object] | None = None


class SourcePlugin(ABC):
    """Abstract base class implemented by all ingestion source plugins."""

    required_config_fields: tuple[str, ...] = ()

    def __init__(self, source_config):
        """Bind a plugin instance to the saved source configuration and project."""

        self.source_config = source_config
        self.project = source_config.project

    @classmethod
    def validate_config(cls, config: object) -> dict:
        """Validate and normalize raw JSON configuration for a plugin.

        Args:
            config: Raw configuration object submitted through admin or API.

        Returns:
            A normalized configuration dictionary.

        Raises:
            ValueError: If the config is not a mapping or required fields are
                missing.
        """

        if not isinstance(config, dict):
            raise ValueError("Config must be a JSON object.")
        normalized_config = dict(config)
        for field_name in cls.required_config_fields:
            if not normalized_config.get(field_name):
                raise ValueError(f"Missing required config field: {field_name}")
        return normalized_config

    @abstractmethod
    def fetch_new_content(self, since: datetime | None) -> list[ContentItem]:
        """Fetch content newer than the given timestamp."""

        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """Return whether the remote source is reachable and usable."""

        raise NotImplementedError

    def match_entity_for_url(self, url: str):
        """Match a fetched URL to a tracked entity based on hostname equality."""

        target_hostname = self._normalize_hostname(url)
        if not target_hostname:
            return None
        for entity in self.project.entities.exclude(website_url=""):
            if self._normalize_hostname(entity.website_url) == target_hostname:
                return entity
        return None

    def match_entity_for_item(self, item: ContentItem):
        """Match a fetched content item to an entity.

        The default implementation preserves the existing hostname-based behavior
        by matching against the normalized item URL.
        """

        return self.match_entity_for_url(item.url)

    @staticmethod
    def _normalize_hostname(url: str) -> str:
        """Normalize a URL hostname for entity matching."""

        hostname = urlparse(url).hostname or ""
        return hostname.removeprefix("www.").lower()
