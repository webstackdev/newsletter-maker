from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group

from core.models import Project, SourceConfig, SourcePluginName
from core.plugins.reddit import RedditSourcePlugin
from core.plugins.registry import validate_plugin_config


pytestmark = pytest.mark.django_db


@pytest.fixture
def reddit_context(django_user_model):
    user = django_user_model.objects.create_user(username="reddit-owner", password="testpass123")
    group = Group.objects.create(name="reddit-team")
    user.groups.add(group)
    project = Project.objects.create(name="Reddit Project", group=group, topic_description="Infra")
    source_config = SourceConfig.objects.create(
        project=project,
        plugin_name=SourcePluginName.REDDIT,
        config={"subreddit": "python", "listing": "both", "limit": 2},
    )
    return SimpleNamespace(project=project, source_config=source_config)


def test_reddit_validate_config_normalizes_defaults_and_rejects_invalid_values():
    assert RedditSourcePlugin.validate_config({"subreddit": "python"}) == {
        "subreddit": "python",
        "listing": "both",
        "limit": 25,
    }

    with pytest.raises(ValueError, match="listing must be one of"):
        RedditSourcePlugin.validate_config({"subreddit": "python", "listing": "top"})

    with pytest.raises(ValueError, match="limit must be a positive integer"):
        RedditSourcePlugin.validate_config({"subreddit": "python", "limit": 0})


def test_validate_plugin_config_rejects_unknown_plugin_name():
    with pytest.raises(ValueError, match="Unsupported source plugin"):
        validate_plugin_config("unknown-plugin", {})


def test_reddit_fetch_new_content_deduplicates_and_filters_by_since(reddit_context, mocker):
    plugin = RedditSourcePlugin(reddit_context.source_config)
    now = datetime.now(tz=UTC)
    duplicate_id = "dup-1"
    old_submission = SimpleNamespace(
        id="old-1",
        url="https://reddit.com/r/python/comments/old-1/test",
        permalink="/r/python/comments/old-1/test",
        title="Old post",
        selftext="Old body",
        author=None,
        created_utc=(now - timedelta(days=2)).timestamp(),
    )
    first_submission = SimpleNamespace(
        id=duplicate_id,
        url="",
        permalink="/r/python/comments/dup-1/test",
        title="  Duplicate title  ",
        selftext="",
        author="redditor",
        created_utc=now.timestamp(),
    )
    duplicate_submission = SimpleNamespace(
        id=duplicate_id,
        url="https://reddit.com/r/python/comments/dup-1/test",
        permalink="/r/python/comments/dup-1/test",
        title="Duplicate title",
        selftext="Ignored duplicate",
        author="redditor",
        created_utc=now.timestamp(),
    )
    subreddit = SimpleNamespace(
        new=lambda limit: iter([old_submission, first_submission]),
        hot=lambda limit: iter([duplicate_submission]),
    )
    client = SimpleNamespace(subreddit=lambda name: subreddit)
    mocker.patch.object(RedditSourcePlugin, "_client", return_value=client)

    items = plugin.fetch_new_content(since=now - timedelta(hours=1))

    assert len(items) == 1
    assert items[0].url == "https://www.reddit.com/r/python/comments/dup-1/test"
    assert items[0].title == "Duplicate title"
    assert items[0].author == "redditor"
    assert items[0].content_text == "Duplicate title"
    assert items[0].source_plugin == SourcePluginName.REDDIT


def test_reddit_health_check_returns_true(reddit_context, mocker):
    plugin = RedditSourcePlugin(reddit_context.source_config)
    subreddit = SimpleNamespace(new=lambda limit: iter([object()]))
    client = SimpleNamespace(subreddit=lambda name: subreddit)
    mocker.patch.object(RedditSourcePlugin, "_client", return_value=client)

    assert plugin.health_check() is True


def test_reddit_client_requires_credentials(settings):
    settings.REDDIT_CLIENT_ID = ""
    settings.REDDIT_CLIENT_SECRET = ""

    with pytest.raises(RuntimeError, match="Reddit credentials are not configured"):
        RedditSourcePlugin._client()


def test_reddit_client_builds_praw_client(settings, mocker):
    settings.REDDIT_CLIENT_ID = "client-id"
    settings.REDDIT_CLIENT_SECRET = "client-secret"
    settings.REDDIT_USER_AGENT = "newsletter-maker-test"
    reddit_cls = mocker.patch("core.plugins.reddit.praw.Reddit", return_value="reddit-client")

    client = RedditSourcePlugin._client()

    assert client == "reddit-client"
    reddit_cls.assert_called_once_with(
        client_id="client-id",
        client_secret="client-secret",
        user_agent="newsletter-maker-test",
    )