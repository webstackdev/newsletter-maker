from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import (
    Content,
    Entity,
    FeedbackType,
    IngestionRun,
    ReviewQueue,
    ReviewReason,
    RunStatus,
    SkillResult,
    SkillStatus,
    SourceConfig,
    SourcePluginName,
    Tenant,
    TenantConfig,
    UserFeedback,
)


class TenantScopedApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="owner", password="testpass123")
        self.other_user = user_model.objects.create_user(username="other", password="testpass123")
        self.owner_tenant = Tenant.objects.create(
            name="Owner Tenant",
            user=self.owner,
            topic_description="Platform engineering",
        )
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant",
            user=self.other_user,
            topic_description="Frontend",
        )
        self.owner_entity = Entity.objects.create(
            tenant=self.owner_tenant,
            name="Owner Entity",
            type="individual",
        )
        self.other_entity = Entity.objects.create(
            tenant=self.other_tenant,
            name="Other Entity",
            type="vendor",
        )
        self.owner_content = Content.objects.create(
            tenant=self.owner_tenant,
            url="https://example.com/owner",
            title="Owner Content",
            author="Owner Author",
            entity=self.owner_entity,
            source_plugin="rss",
            published_date="2026-04-21T00:00:00Z",
            content_text="Owner content text",
        )
        self.other_content = Content.objects.create(
            tenant=self.other_tenant,
            url="https://example.com/other",
            title="Other Content",
            author="Other Author",
            entity=self.other_entity,
            source_plugin="rss",
            published_date="2026-04-21T00:00:00Z",
            content_text="Other content text",
        )
        self.owner_config = TenantConfig.objects.create(tenant=self.owner_tenant)
        self.owner_skill_result = SkillResult.objects.create(
            tenant=self.owner_tenant,
            content=self.owner_content,
            skill_name="summarization",
            status=SkillStatus.COMPLETED,
            result_data={"summary": "Owner summary"},
        )
        self.owner_ingestion_run = IngestionRun.objects.create(
            tenant=self.owner_tenant,
            plugin_name="rss",
            status=RunStatus.SUCCESS,
            items_fetched=5,
            items_ingested=4,
        )
        self.owner_review_queue = ReviewQueue.objects.create(
            tenant=self.owner_tenant,
            content=self.owner_content,
            reason=ReviewReason.BORDERLINE_RELEVANCE,
            confidence=0.51,
        )
        self.owner_source_config = SourceConfig.objects.create(
            tenant=self.owner_tenant,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
        )
        self.client.force_authenticate(self.owner)

    def assert_standardized_validation_error(self, payload, attr):
        self.assertEqual(payload["type"], "validation_error")
        self.assertTrue(any(error["attr"] == attr for error in payload["errors"]))

    def test_tenant_list_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse("v1:tenant-list"), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.json(),
            {
                "type": "client_error",
                "errors": [
                    {
                        "code": "not_authenticated",
                        "detail": "Authentication credentials were not provided.",
                        "attr": None,
                    }
                ],
            },
        )

    def test_tenant_list_is_scoped_to_request_user(self):
        response = self.client.get(reverse("v1:tenant-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], self.owner_tenant.id)

    def test_entity_list_is_scoped_to_request_user_tenant(self):
        response = self.client.get(reverse("v1:tenant-entity-list", kwargs={"tenant_id": self.owner_tenant.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], self.owner_entity.id)

    def test_nested_entity_list_rejects_other_users_tenant(self):
        response = self.client.get(reverse("v1:tenant-entity-list", kwargs={"tenant_id": self.other_tenant.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_feedback_create_assigns_current_user(self):
        response = self.client.post(
            reverse("v1:tenant-feedback-list", kwargs={"tenant_id": self.owner_tenant.id}),
            {
                "content": self.owner_content.id,
                "feedback_type": FeedbackType.UPVOTE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        feedback = UserFeedback.objects.get()
        self.assertEqual(feedback.user, self.owner)
        self.assertEqual(feedback.feedback_type, FeedbackType.UPVOTE)

    def test_feedback_rejects_cross_tenant_content(self):
        response = self.client.post(
            reverse("v1:tenant-feedback-list", kwargs={"tenant_id": self.owner_tenant.id}),
            {
                "content": self.other_content.id,
                "feedback_type": FeedbackType.DOWNVOTE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_standardized_validation_error(response.json(), "content")

    def test_content_create_uses_tenant_from_url(self):
        response = self.client.post(
            reverse("v1:tenant-content-list", kwargs={"tenant_id": self.owner_tenant.id}),
            {
                "url": "https://example.com/new",
                "title": "New Content",
                "author": "Owner Author",
                "entity": self.owner_entity.id,
                "source_plugin": "rss",
                "published_date": "2026-04-22T00:00:00Z",
                "content_text": "Nested content text",
                "tenant": self.other_tenant.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_content = Content.objects.get(title="New Content")
        self.assertEqual(created_content.tenant, self.owner_tenant)

    def test_authenticated_nested_list_endpoints_smoke(self):
        list_endpoints = [
            reverse("v1:tenant-config-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-entity-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-content-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-skill-result-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-feedback-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-ingestion-run-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-source-config-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-review-queue-list", kwargs={"tenant_id": self.owner_tenant.id}),
        ]

        for endpoint in list_endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_nested_detail_endpoints_smoke(self):
        detail_endpoints = [
            reverse(
                "v1:tenant-config-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_config.id},
            ),
            reverse(
                "v1:tenant-entity-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_entity.id},
            ),
            reverse(
                "v1:tenant-content-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_content.id},
            ),
            reverse(
                "v1:tenant-skill-result-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_skill_result.id},
            ),
            reverse(
                "v1:tenant-ingestion-run-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_ingestion_run.id},
            ),
            reverse(
                "v1:tenant-source-config-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_source_config.id},
            ),
            reverse(
                "v1:tenant-review-queue-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_review_queue.id},
            ),
        ]

        feedback = UserFeedback.objects.create(
            tenant=self.owner_tenant,
            content=self.owner_content,
            user=self.owner,
            feedback_type=FeedbackType.UPVOTE,
        )
        detail_endpoints.append(
            reverse(
                "v1:tenant-feedback-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": feedback.id},
            )
        )

        for endpoint in detail_endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_source_config_create_validates_plugin_config(self):
        response = self.client.post(
            reverse("v1:tenant-source-config-list", kwargs={"tenant_id": self.owner_tenant.id}),
            {"plugin_name": SourcePluginName.RSS, "config": {}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_standardized_validation_error(response.json(), "config")
