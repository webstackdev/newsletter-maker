from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group

from core.models import (
    BlueskyCredentials,
    Entity,
    Project,
    SourceConfig,
    SourcePluginName,
)
from core.plugins.bluesky import BlueskySourcePlugin

pytestmark = pytest.mark.django_db


@pytest.fixture
def bluesky_context(django_user_model):
    user = django_user_model.objects.create_user(
        username="bluesky-owner", password="testpass123"
    )
    group = Group.objects.create(name="bluesky-team")
    user.groups.add(group)
    project = Project.objects.create(
        name="Bluesky Project", group=group, topic_description="Infra"
    )
    entity = Entity.objects.create(
        project=project,
        name="Alice",
        type="person",
        bluesky_handle="alice.bsky.social",
        website_url="https://example.com/company",
    )
    source_config = SourceConfig.objects.create(
        project=project,
        plugin_name=SourcePluginName.BLUESKY,
        config={"author_handle": "alice.bsky.social"},
    )
    return SimpleNamespace(project=project, entity=entity, source_config=source_config)


def test_bluesky_validate_config_normalizes_defaults_and_rejects_invalid_values():
    assert BlueskySourcePlugin.validate_config({"author_handle": "@Alice.BSKY.social"}) == {
        "author_handle": "alice.bsky.social",
        "include_replies": False,
        "max_posts_per_fetch": 100,
    }

    assert BlueskySourcePlugin.validate_config(
        {
            "feed_uri": "at://did:plc:alice/app.bsky.feed.generator/news",
            "include_replies": True,
            "max_posts_per_fetch": "5",
        }
    ) == {
        "feed_uri": "at://did:plc:alice/app.bsky.feed.generator/news",
        "include_replies": True,
        "max_posts_per_fetch": 5,
    }

    with pytest.raises(ValueError, match="Provide exactly one"):
        BlueskySourcePlugin.validate_config({})

    with pytest.raises(ValueError, match="Provide exactly one"):
        BlueskySourcePlugin.validate_config(
            {
                "feed_uri": "at://did:plc:alice/app.bsky.feed.generator/news",
                "author_handle": "alice.bsky.social",
            }
        )

    with pytest.raises(ValueError, match="feed_uri must be a Bluesky feed generator"):
        BlueskySourcePlugin.validate_config({"feed_uri": "https://example.com/feed"})

    with pytest.raises(ValueError, match="max_posts_per_fetch must be a positive integer"):
        BlueskySourcePlugin.validate_config(
            {"author_handle": "alice.bsky.social", "max_posts_per_fetch": 0}
        )

    with pytest.raises(ValueError, match="include_replies must be a boolean"):
        BlueskySourcePlugin.validate_config(
            {"author_handle": "alice.bsky.social", "include_replies": "yes"}
        )


def test_bluesky_fetch_new_content_prefers_embedded_links_and_filters_replies(
    bluesky_context, mocker
):
    plugin = BlueskySourcePlugin(bluesky_context.source_config)
    now = datetime.now(tz=UTC)
    iso_now = now.isoformat().replace("+00:00", "Z")
    old_iso = (now - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    old_post = SimpleNamespace(
        uri="at://did:plc:alice/app.bsky.feed.post/old",
        indexed_at=old_iso,
        author=SimpleNamespace(did="did:plc:alice", handle="Alice.BSky.social"),
        record=SimpleNamespace(text="Old post", created_at=old_iso),
        reply_count=0,
        repost_count=0,
        embed=None,
    )
    reply_post = SimpleNamespace(
        uri="at://did:plc:alice/app.bsky.feed.post/reply",
        indexed_at=iso_now,
        author=SimpleNamespace(did="did:plc:alice", handle="Alice.BSky.social"),
        record=SimpleNamespace(text="A reply", created_at=iso_now),
        reply_count=1,
        repost_count=0,
        embed=None,
    )
    linked_post = SimpleNamespace(
        uri="at://did:plc:alice/app.bsky.feed.post/fresh",
        indexed_at=iso_now,
        author=SimpleNamespace(did="did:plc:alice", handle="Alice.BSky.social"),
        record=SimpleNamespace(text="  Check this out  ", created_at=iso_now),
        embed=SimpleNamespace(
            external=SimpleNamespace(
                uri="https://example.com/article",
                title="  Linked article  ",
            )
        ),
        reply_count=2,
        repost_count=3,
    )
    duplicate_post = SimpleNamespace(
        uri="at://did:plc:alice/app.bsky.feed.post/fresh",
        indexed_at=iso_now,
        author=SimpleNamespace(did="did:plc:alice", handle="Alice.BSky.social"),
        record=SimpleNamespace(text="Duplicate", created_at=iso_now),
        reply_count=0,
        repost_count=0,
        embed=None,
    )
    mocker.patch.object(
        BlueskySourcePlugin,
        "_get_feed_response",
        return_value=SimpleNamespace(
            feed=[
                SimpleNamespace(post=old_post, reply=None),
                SimpleNamespace(post=reply_post, reply=object()),
                SimpleNamespace(post=linked_post, reply=None),
                SimpleNamespace(post=duplicate_post, reply=None),
            ]
        ),
    )

    items = plugin.fetch_new_content(since=now - timedelta(hours=1))

    assert len(items) == 1
    assert items[0].url == "https://example.com/article"
    assert items[0].title == "Linked article"
    assert items[0].author == "alice.bsky.social"
    assert items[0].content_text == "Check this out"
    assert items[0].source_plugin == SourcePluginName.BLUESKY
    assert items[0].source_metadata == {
        "author_did": "did:plc:alice",
        "author_handle": "alice.bsky.social",
        "embedded_url": "https://example.com/article",
        "post_uri": "at://did:plc:alice/app.bsky.feed.post/fresh",
        "reply_count": 2,
        "repost_count": 3,
    }


def test_bluesky_match_entity_for_item_uses_bluesky_handle(bluesky_context):
    plugin = BlueskySourcePlugin(bluesky_context.source_config)

    result = plugin.match_entity_for_item(
        SimpleNamespace(
            url="https://irrelevant.example.com/article",
            source_metadata={"author_handle": "Alice.BSky.social"},
        )
    )

    assert result == bluesky_context.entity


def test_bluesky_health_check_queries_configured_endpoint(bluesky_context, mocker):
    client = SimpleNamespace(
        app=SimpleNamespace(
            bsky=SimpleNamespace(
                feed=SimpleNamespace(
                    get_author_feed=mocker.Mock(return_value=SimpleNamespace(feed=[]))
                )
            )
        )
    )
    mocker.patch.object(BlueskySourcePlugin, "_client", return_value=client)

    plugin = BlueskySourcePlugin(bluesky_context.source_config)

    assert plugin.health_check() is True
    client.app.bsky.feed.get_author_feed.assert_called_once_with(
        {"actor": "alice.bsky.social", "include_pins": False, "limit": 1}
    )


def test_bluesky_credentials_encrypt_password_and_normalize_pds_url(bluesky_context):
    credentials = BlueskyCredentials(
        project=bluesky_context.project,
        handle="@Alice.BSKY.social",
        pds_url="https://pds.example.com/xrpc/",
    )
    credentials.set_app_password("app-password")
    credentials.save()
    credentials.refresh_from_db()

    assert credentials.handle == "alice.bsky.social"
    assert credentials.pds_url == "https://pds.example.com"
    assert credentials.client_base_url == "https://pds.example.com/xrpc"
    assert credentials.app_password_encrypted != "app-password"
    assert credentials.get_app_password() == "app-password"


def test_bluesky_client_uses_authenticated_project_credentials(
    bluesky_context, mocker
):
    credentials = BlueskyCredentials(project=bluesky_context.project, handle="alice.bsky.social")
    credentials.set_app_password("app-password")
    credentials.save()
    client = mocker.Mock()
    client_cls = mocker.patch("core.plugins.bluesky.Client", return_value=client)

    plugin = BlueskySourcePlugin(bluesky_context.source_config)

    assert plugin._client() == client
    client_cls.assert_called_once_with(base_url="https://bsky.social/xrpc")
    client.login.assert_called_once_with(
        login="alice.bsky.social", password="app-password"
    )


def test_bluesky_health_check_records_credential_errors(bluesky_context, mocker):
    credentials = BlueskyCredentials(project=bluesky_context.project, handle="alice.bsky.social")
    credentials.set_app_password("app-password")
    credentials.save()
    plugin = BlueskySourcePlugin(bluesky_context.source_config)
    mocker.patch.object(
        BlueskySourcePlugin, "_get_feed_response", side_effect=RuntimeError("bad login")
    )

    with pytest.raises(RuntimeError, match="bad login"):
        plugin.health_check()

    credentials.refresh_from_db()
    assert credentials.last_error == "bad login"
    assert credentials.last_verified_at is None


def test_bluesky_verify_credentials_uses_authenticated_session_check(
    bluesky_context, mocker
):
    credentials = BlueskyCredentials(project=bluesky_context.project, handle="alice.bsky.social")
    credentials.set_app_password("app-password")
    credentials.save()
    client = mocker.Mock()
    client_cls = mocker.patch("core.plugins.bluesky.Client", return_value=client)

    BlueskySourcePlugin.verify_credentials(credentials)

    client_cls.assert_called_once_with(base_url="https://bsky.social/xrpc")
    client.login.assert_called_once_with(
        login="alice.bsky.social", password="app-password"
    )
    client.com.atproto.server.get_session.assert_called_once_with()
    credentials.refresh_from_db()
    assert credentials.last_error == ""
    assert credentials.last_verified_at is not None
