from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser, Group

from core.models import (
    Content,
    Entity,
    Project,
    ReviewReason,
    SkillResult,
    SourceConfig,
    SourcePluginName,
)
from core.serializers import (
    ContentSerializer,
    EntitySerializer,
    IngestionRunSerializer,
    ProjectSerializer,
    ReviewQueueSerializer,
    SkillResultSerializer,
    SourceConfigSerializer,
    UserFeedbackSerializer,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def serializer_context(django_user_model):
    user = django_user_model.objects.create_user(
        username="serializer-owner", password="testpass123"
    )
    other_user = django_user_model.objects.create_user(
        username="serializer-other", password="testpass123"
    )
    group = Group.objects.create(name="serializer-team")
    other_group = Group.objects.create(name="serializer-other-team")
    user.groups.add(group)
    other_user.groups.add(other_group)
    project = Project.objects.create(
        name="Serializer Project", group=group, topic_description="Infra"
    )
    other_project = Project.objects.create(
        name="Other Serializer Project", group=other_group, topic_description="Data"
    )
    entity = Entity.objects.create(
        project=project, name="Serializer Entity", type="vendor"
    )
    other_entity = Entity.objects.create(
        project=other_project, name="Other Entity", type="vendor"
    )
    content = Content.objects.create(
        project=project,
        url="https://example.com/serializer-content",
        title="Serializer Content",
        author="Author",
        entity=entity,
        source_plugin=SourcePluginName.RSS,
        published_date="2026-04-28T00:00:00Z",
        content_text="Serializer content body.",
    )
    other_content = Content.objects.create(
        project=other_project,
        url="https://example.com/serializer-other-content",
        title="Other Content",
        author="Author",
        entity=other_entity,
        source_plugin=SourcePluginName.RSS,
        published_date="2026-04-28T00:00:00Z",
        content_text="Other serializer content body.",
    )
    skill_result = SkillResult.objects.create(
        project=project,
        content=content,
        skill_name="summarization",
        status="completed",
        result_data={"summary": "ok"},
    )
    other_skill_result = SkillResult.objects.create(
        project=other_project,
        content=other_content,
        skill_name="summarization",
        status="completed",
        result_data={"summary": "other"},
    )
    return SimpleNamespace(
        user=user,
        other_user=other_user,
        project=project,
        other_project=other_project,
        entity=entity,
        other_entity=other_entity,
        content=content,
        other_content=other_content,
        skill_result=skill_result,
        other_skill_result=other_skill_result,
    )


def _request_for(user):
    return SimpleNamespace(user=user)


def test_project_scoped_serializer_filters_related_querysets_with_project_context(
    serializer_context,
):
    serializer = SkillResultSerializer(
        context={
            "request": _request_for(serializer_context.user),
            "project": serializer_context.project,
        }
    )

    assert list(serializer.fields["content"].queryset) == [serializer_context.content]
    assert list(serializer.fields["superseded_by"].queryset) == [
        serializer_context.skill_result
    ]
    assert list(serializer.fields["project"].queryset) == [serializer_context.project]


def test_project_scoped_serializer_filters_related_querysets_without_project_context(
    serializer_context,
):
    serializer = ContentSerializer(
        context={"request": _request_for(serializer_context.user)}
    )

    assert list(serializer.fields["entity"].queryset) == [serializer_context.entity]
    assert list(serializer.fields["project"].queryset) == [serializer_context.project]


def test_project_scoped_serializer_skips_filtering_for_anonymous_user():
    serializer = ProjectSerializer(context={"request": _request_for(AnonymousUser())})

    assert serializer.fields["group"].queryset.count() == Group.objects.count()


def test_content_serializer_rejects_cross_project_entity(serializer_context):
    serializer = ContentSerializer(
        instance=serializer_context.content,
        data={"entity": serializer_context.other_entity.id},
        partial=True,
        context={"project": serializer_context.project},
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {
        "entity": ["Entity must belong to the selected project."]
    }


def test_skill_result_serializer_rejects_cross_project_content(serializer_context):
    serializer = SkillResultSerializer(
        data={
            "content": serializer_context.other_content.id,
            "skill_name": "summarization",
            "status": "completed",
        },
        context={
            "project": serializer_context.project,
        },
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {
        "content": ["Content must belong to the selected project."]
    }


def test_review_queue_serializer_rejects_cross_project_content(serializer_context):
    serializer = ReviewQueueSerializer(
        data={
            "content": serializer_context.other_content.id,
            "reason": ReviewReason.BORDERLINE_RELEVANCE,
            "confidence": 0.5,
        },
        context={
            "project": serializer_context.project,
        },
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {
        "content": ["Content must belong to the selected project."]
    }


def test_source_config_serializer_normalizes_valid_config(serializer_context):
    serializer = SourceConfigSerializer(
        data={
            "plugin_name": SourcePluginName.RSS,
            "config": {"feed_url": "https://example.com/feed.xml"},
            "is_active": True,
        },
        context={
            "request": _request_for(serializer_context.user),
            "project": serializer_context.project,
        },
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["config"] == {
        "feed_url": "https://example.com/feed.xml"
    }


def test_source_config_serializer_surfaces_plugin_validation_errors(serializer_context):
    serializer = SourceConfigSerializer(
        instance=SourceConfig(
            project=serializer_context.project,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
        ),
        data={"config": {"feed_url": ""}},
        partial=True,
        context={
            "request": _request_for(serializer_context.user),
            "project": serializer_context.project,
        },
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {"config": ["Missing required config field: feed_url"]}


def test_source_config_serializer_normalizes_bluesky_author_handle_config(
    serializer_context,
):
    serializer = SourceConfigSerializer(
        data={
            "plugin_name": SourcePluginName.BLUESKY,
            "config": {"author_handle": "@Alice.BSKY.social"},
            "is_active": True,
        },
        context={
            "request": _request_for(serializer_context.user),
            "project": serializer_context.project,
        },
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["config"] == {
        "author_handle": "alice.bsky.social",
        "include_replies": False,
        "max_posts_per_fetch": 100,
    }


def test_entity_serializer_filters_project_queryset_to_request_user(serializer_context):
    serializer = EntitySerializer(
        context={"request": _request_for(serializer_context.user)}
    )

    assert list(serializer.fields["project"].queryset) == [serializer_context.project]


def test_user_feedback_serializer_rejects_cross_project_content(serializer_context):
    serializer = UserFeedbackSerializer(
        data={
            "content": serializer_context.other_content.id,
            "feedback_type": "upvote",
        },
        context={
            "project": serializer_context.project,
        },
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {
        "content": ["Content must belong to the selected project."]
    }


def test_review_queue_serializer_accepts_same_project_content(serializer_context):
    serializer = ReviewQueueSerializer(
        data={
            "content": serializer_context.content.id,
            "reason": ReviewReason.BORDERLINE_RELEVANCE,
            "confidence": 0.5,
        },
        context={
            "project": serializer_context.project,
        },
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["content"] == serializer_context.content


def test_source_config_serializer_skips_plugin_validation_when_plugin_name_missing(
    serializer_context,
):
    serializer = SourceConfigSerializer(
        instance=SourceConfig(
            project=serializer_context.project, plugin_name="", config={}
        ),
        data={"config": {}},
        partial=True,
        context={
            "project": serializer_context.project,
        },
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["config"] == {}


def test_ingestion_run_serializer_filters_project_queryset(serializer_context):
    serializer = IngestionRunSerializer(
        context={"request": _request_for(serializer_context.user)}
    )

    assert list(serializer.fields["project"].queryset) == [serializer_context.project]
