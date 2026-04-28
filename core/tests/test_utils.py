import pytest
from django.contrib.auth.models import Group

from core.models import Project, ProjectConfig
from core.utils import dashboard_callback


pytestmark = pytest.mark.django_db


def test_dashboard_callback_uses_zero_when_no_project_configs():
    context = {"existing": True}

    result = dashboard_callback(request=None, context=context)

    assert result["existing"] is True
    assert result["avg_authority_weight"] == 0


def test_dashboard_callback_rounds_average_authority_weight(django_user_model):
    user = django_user_model.objects.create_user(username="utils-owner", password="testpass123")
    group = Group.objects.create(name="utils-team")
    user.groups.add(group)
    project_one = Project.objects.create(name="Utils Project 1", group=group, topic_description="Infra")
    project_two = Project.objects.create(name="Utils Project 2", group=group, topic_description="Data")
    ProjectConfig.objects.create(project=project_one, upvote_authority_weight=0.1234)
    ProjectConfig.objects.create(project=project_two, upvote_authority_weight=0.5678)

    result = dashboard_callback(request=None, context={})

    assert result["avg_authority_weight"] == 0.35