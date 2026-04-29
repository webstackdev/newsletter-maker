"""Bluesky source plugin used to ingest public feeds and author timelines."""

from __future__ import annotations

from datetime import datetime

from atproto import Client
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.models import BlueskyCredentials, SourcePluginName
from core.plugins.base import ContentItem, SourcePlugin

PUBLIC_APPVIEW_BASE_URL = "https://public.api.bsky.app"


class BlueskySourcePlugin(SourcePlugin):
    """Fetch public Bluesky feed or author posts through AppView."""

    @classmethod
    def verify_credentials(cls, credentials: BlueskyCredentials) -> None:
        """Authenticate a stored Bluesky account and confirm the session works."""

        try:
            client = cls._authenticated_client_for_credentials(credentials)
            client.com.atproto.server.get_session()
        except Exception as exc:
            cls._record_credentials_status(credentials, error_message=str(exc))
            raise
        cls._record_credentials_status(credentials, error_message="")

    @classmethod
    def validate_config(cls, config: object) -> dict:
        """Validate Bluesky feed or author configuration."""

        normalized_config = super().validate_config(config)
        feed_uri = normalized_config.get("feed_uri")
        author_handle = normalized_config.get("author_handle")
        if bool(feed_uri) == bool(author_handle):
            raise ValueError("Provide exactly one of feed_uri or author_handle")
        if feed_uri and (
            not isinstance(feed_uri, str)
            or not feed_uri.startswith("at://")
            or "/app.bsky.feed.generator/" not in feed_uri
        ):
            raise ValueError(
                "feed_uri must be a Bluesky feed generator at:// URI"
            )
        if author_handle:
            normalized_handle = cls._normalize_handle(author_handle)
            if not normalized_handle:
                raise ValueError("author_handle must be a non-empty Bluesky handle")
            normalized_config["author_handle"] = normalized_handle

        normalized_config["max_posts_per_fetch"] = int(
            normalized_config.get("max_posts_per_fetch", 100)
        )
        if normalized_config["max_posts_per_fetch"] <= 0:
            raise ValueError("max_posts_per_fetch must be a positive integer")

        include_replies = normalized_config.get("include_replies", False)
        if not isinstance(include_replies, bool):
            raise ValueError("include_replies must be a boolean")
        normalized_config["include_replies"] = include_replies
        return normalized_config

    def fetch_new_content(self, since: datetime | None) -> list[ContentItem]:
        """Fetch public Bluesky posts newer than ``since`` and normalize them."""

        response = self._get_feed_response()
        items: list[ContentItem] = []
        seen_post_uris: set[str] = set()
        for feed_view in response.feed:
            post = getattr(feed_view, "post", None)
            if post is None or post.uri in seen_post_uris:
                continue
            seen_post_uris.add(post.uri)
            if not self.source_config.config.get("include_replies", False) and getattr(
                feed_view, "reply", None
            ):
                continue
            published_date = self._published_date_for_post(post)
            if since and published_date <= since:
                continue
            items.append(self._build_content_item(post, published_date))
        return items

    def health_check(self) -> bool:
        """Treat the source as healthy when the AppView request succeeds."""

        credentials = self._credentials()
        try:
            self._get_feed_response(limit=1)
        except Exception as exc:
            self._record_credentials_status(credentials, error_message=str(exc))
            raise
        self._record_credentials_status(credentials, error_message="")
        return True

    def match_entity_for_item(self, item: ContentItem):
        """Match posts to entities using the author's Bluesky handle first."""

        author_handle = self._normalize_handle(
            str((item.source_metadata or {}).get("author_handle", ""))
        )
        if author_handle:
            for entity in self.project.entities.exclude(bluesky_handle=""):
                if self._normalize_handle(entity.bluesky_handle) == author_handle:
                    return entity
        return super().match_entity_for_item(item)

    def _get_feed_response(self, limit: int | None = None):
        """Query the configured public feed endpoint."""

        request_limit = limit or self.source_config.config.get("max_posts_per_fetch", 100)
        client = self._client()
        feed_uri = self.source_config.config.get("feed_uri")
        if feed_uri:
            return client.app.bsky.feed.get_feed(
                {"feed": feed_uri, "limit": request_limit}
            )
        return client.app.bsky.feed.get_author_feed(
            {
                "actor": self.source_config.config["author_handle"],
                "include_pins": False,
                "limit": request_limit,
            }
        )

    def _build_content_item(self, post, published_date: datetime) -> ContentItem:
        """Convert one AppView post into the shared plugin payload."""

        author_handle = self._normalize_handle(self._nested_value(post, "author", "handle"))
        external_url = self._nested_value(post, "embed", "external", "uri")
        external_title = (
            self._nested_value(post, "embed", "external", "title") or ""
        ).strip()
        post_url = self._post_url(post)
        record_text = (self._nested_value(post, "record", "text") or "").strip()
        title = external_title or record_text.splitlines()[0].strip() or post_url
        return ContentItem(
            url=external_url or post_url,
            title=title,
            author=author_handle,
            published_date=published_date,
            content_text=record_text or external_title or post_url,
            source_plugin=SourcePluginName.BLUESKY,
            source_metadata={
                "author_did": self._nested_value(post, "author", "did") or "",
                "author_handle": author_handle,
                "embedded_url": external_url or "",
                "post_uri": getattr(post, "uri", ""),
                "reply_count": getattr(post, "reply_count", 0) or 0,
                "repost_count": getattr(post, "repost_count", 0) or 0,
            },
        )

    @staticmethod
    def _published_date_for_post(post) -> datetime:
        """Choose the indexed or record timestamp for a Bluesky post."""

        for value in (
            getattr(post, "indexed_at", None),
            BlueskySourcePlugin._nested_value(post, "record", "created_at"),
        ):
            if value:
                parsed_value = parse_datetime(value)
                if parsed_value is not None:
                    return parsed_value
        return timezone.now()

    @staticmethod
    def _post_url(post) -> str:
        """Build the public web URL for a Bluesky post when no card link exists."""

        actor = (
            BlueskySourcePlugin._normalize_handle(
                BlueskySourcePlugin._nested_value(post, "author", "handle")
            )
            or BlueskySourcePlugin._nested_value(post, "author", "did")
            or ""
        )
        post_uri = getattr(post, "uri", "")
        post_id = post_uri.rstrip("/").split("/")[-1] if post_uri else ""
        if actor and post_id:
            return f"https://bsky.app/profile/{actor}/post/{post_id}"
        return post_uri

    @staticmethod
    def _normalize_handle(handle: object) -> str:
        """Normalize handles so matching stays case-insensitive."""

        if not isinstance(handle, str):
            return ""
        return handle.strip().removeprefix("@").lower()

    @staticmethod
    def _nested_value(value, *path: str):
        """Read nested object or dict attributes without binding to model types."""

        current_value = value
        for path_part in path:
            if current_value is None:
                return None
            if isinstance(current_value, dict):
                current_value = current_value.get(path_part)
            else:
                current_value = getattr(current_value, path_part, None)
        return current_value

    def _client(self) -> Client:
        """Create a public or authenticated ATProto client for the project."""

        credentials = self._credentials()
        if credentials is None:
            return Client(base_url=PUBLIC_APPVIEW_BASE_URL)
        return self._authenticated_client_for_credentials(credentials)

    def _credentials(self) -> BlueskyCredentials | None:
        """Return the active project-scoped Bluesky credentials, if configured."""

        return BlueskyCredentials.objects.filter(project=self.project, is_active=True).first()

    @staticmethod
    def _authenticated_client_for_credentials(credentials: BlueskyCredentials) -> Client:
        """Build an authenticated client from a stored credential record."""

        if not credentials.has_app_password():
            raise RuntimeError("Bluesky credentials are missing an app password.")
        client = Client(base_url=credentials.client_base_url)
        client.login(login=credentials.handle, password=credentials.get_app_password())
        return client

    @staticmethod
    def _record_credentials_status(
        credentials: BlueskyCredentials | None, *, error_message: str
    ) -> None:
        """Persist the latest credential verification result when credentials exist."""

        if credentials is None:
            return
        update_fields = ["last_error", "updated_at"]
        credentials.last_error = error_message
        if not error_message:
            credentials.last_verified_at = timezone.now()
            update_fields.append("last_verified_at")
        credentials.save(update_fields=update_fields)
