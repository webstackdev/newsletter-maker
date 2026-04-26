from typing import Any

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, viewsets
from rest_framework.exceptions import NotFound

from core.models import (
    Content,
    Entity,
    IngestionRun,
    ReviewQueue,
    SkillResult,
    SourceConfig,
    Tenant,
    TenantConfig,
    UserFeedback,
)
from core.serializers import (
    ContentSerializer,
    EntitySerializer,
    IngestionRunSerializer,
    ReviewQueueSerializer,
    SkillResultSerializer,
    SourceConfigSerializer,
    TenantConfigSerializer,
    TenantSerializer,
    UserFeedbackSerializer,
)

TENANT_ID_PARAMETER = OpenApiParameter(
    name="tenant_id",
    type=int,
    location=OpenApiParameter.PATH,
    description="The unique ID of the tenant that owns this nested resource.",
)

TENANT_CREATE_REQUEST_EXAMPLE = OpenApiExample(
    "Create Tenant Request",
    value={
        "name": "AI Weekly",
        "topic_description": "Coverage of developer tools, model releases, and applied AI workflows.",
        "content_retention_days": 180,
    },
    request_only=True,
)

TENANT_RESPONSE_EXAMPLE = OpenApiExample(
    "Tenant Response",
    value={
        "id": 1,
        "name": "AI Weekly",
        "user": 7,
        "topic_description": "Coverage of developer tools, model releases, and applied AI workflows.",
        "content_retention_days": 180,
        "created_at": "2026-04-26T12:00:00Z",
    },
    response_only=True,
)

SOURCE_CONFIG_CREATE_REQUEST_EXAMPLE = OpenApiExample(
    "Create RSS Source Request",
    value={
        "plugin_name": "rss",
        "config": {
            "feed_url": "https://example.com/feed.xml",
        },
        "is_active": True,
    },
    request_only=True,
)

SOURCE_CONFIG_REDDIT_REQUEST_EXAMPLE = OpenApiExample(
    "Create Reddit Source Request",
    value={
        "plugin_name": "reddit",
        "config": {
            "subreddit": "MachineLearning",
            "listing": "both",
            "limit": 25,
        },
        "is_active": True,
    },
    request_only=True,
)

SOURCE_CONFIG_RESPONSE_EXAMPLE = OpenApiExample(
    "Source Configuration Response",
    value={
        "id": 12,
        "tenant": 1,
        "plugin_name": "rss",
        "config": {
            "feed_url": "https://example.com/feed.xml",
        },
        "is_active": True,
        "last_fetched_at": "2026-04-26T12:30:00Z",
    },
    response_only=True,
)

CONTENT_CREATE_REQUEST_EXAMPLE = OpenApiExample(
    "Create Content Request",
    value={
        "url": "https://example.com/posts/agent-memory-patterns",
        "title": "Practical Agent Memory Patterns",
        "author": "Jane Doe",
        "entity": 4,
        "source_plugin": "rss",
        "content_type": "article",
        "published_date": "2026-04-25T14:00:00Z",
        "content_text": "A walkthrough of short-term and long-term memory patterns for production agents.",
        "relevance_score": 0.92,
        "is_reference": False,
        "is_active": True,
    },
    request_only=True,
)

CONTENT_RESPONSE_EXAMPLE = OpenApiExample(
    "Content Response",
    value={
        "id": 44,
        "tenant": 1,
        "url": "https://example.com/posts/agent-memory-patterns",
        "title": "Practical Agent Memory Patterns",
        "author": "Jane Doe",
        "entity": 4,
        "source_plugin": "rss",
        "content_type": "article",
        "published_date": "2026-04-25T14:00:00Z",
        "ingested_at": "2026-04-26T12:05:00Z",
        "content_text": "A walkthrough of short-term and long-term memory patterns for production agents.",
        "relevance_score": 0.92,
        "embedding_id": "emb_01jabcxyz",
        "is_reference": False,
        "is_active": True,
    },
    response_only=True,
)

SKILL_RESULT_RESPONSE_EXAMPLE = OpenApiExample(
    "Skill Result Response",
    value={
        "id": 91,
        "content": 44,
        "tenant": 1,
        "skill_name": "relevance_classifier",
        "status": "completed",
        "result_data": {
            "label": "high_relevance",
            "reasoning": "The article directly covers agent memory design patterns.",
        },
        "error_message": "",
        "model_used": "gpt-4.1-mini",
        "latency_ms": 842,
        "confidence": 0.97,
        "created_at": "2026-04-26T12:06:00Z",
        "superseded_by": None,
    },
    response_only=True,
)

AUTHENTICATION_REQUIRED_EXAMPLE = OpenApiExample(
    "Authentication Required",
    value={
        "type": "client_error",
        "errors": [
            {
                "code": "not_authenticated",
                "detail": "Authentication credentials were not provided.",
                "attr": None,
            }
        ],
    },
    response_only=True,
    status_codes=["403"],
)

AUTHENTICATION_REQUIRED_RESPONSE = OpenApiResponse(
    response=inline_serializer(
        name="AuthenticationRequiredResponse",
        fields={
            "type": serializers.CharField(),
            "errors": inline_serializer(
                name="AuthenticationRequiredError",
                fields={
                    "code": serializers.CharField(),
                    "detail": serializers.CharField(),
                    "attr": serializers.CharField(allow_null=True),
                },
                many=True,
            ),
        },
    ),
    description="Authentication credentials are required to access this endpoint.",
    examples=[AUTHENTICATION_REQUIRED_EXAMPLE],
)


def build_success_response(response, description: str, examples: list[OpenApiExample] | None = None):
    response_kwargs = {
        "response": response,
        "description": description,
    }
    if examples is not None:
        response_kwargs["examples"] = examples
    return OpenApiResponse(**response_kwargs)


def build_crud_action_overrides(
    serializer_class,
    resource_plural: str,
    resource_singular: str,
    *,
    list_examples: list[OpenApiExample] | None = None,
    retrieve_examples: list[OpenApiExample] | None = None,
    create_examples: list[OpenApiExample] | None = None,
    create_response_examples: list[OpenApiExample] | None = None,
):
    overrides: dict[str, dict[str, Any]] = {
        "list": {
            "responses": {
                200: build_success_response(
                    serializer_class(many=True),
                    f"A list of {resource_plural}.",
                    examples=list_examples if list_examples is not None else [],
                ),
                403: AUTHENTICATION_REQUIRED_RESPONSE,
            }
        },
        "retrieve": {
            "responses": {
                200: build_success_response(
                    serializer_class,
                    f"The requested {resource_singular}.",
                    examples=retrieve_examples,
                ),
                403: AUTHENTICATION_REQUIRED_RESPONSE,
            }
        },
        "create": {
            "responses": {
                201: build_success_response(
                    serializer_class,
                    f"The newly created {resource_singular}.",
                    examples=create_response_examples,
                ),
                403: AUTHENTICATION_REQUIRED_RESPONSE,
            }
        },
        "update": {
            "responses": {
                200: build_success_response(serializer_class, f"The updated {resource_singular}."),
                403: AUTHENTICATION_REQUIRED_RESPONSE,
            }
        },
        "partial_update": {
            "responses": {
                200: build_success_response(serializer_class, f"The updated {resource_singular}."),
                403: AUTHENTICATION_REQUIRED_RESPONSE,
            }
        },
        "destroy": {
            "responses": {
                204: OpenApiResponse(description=f"The {resource_singular} was deleted."),
                403: AUTHENTICATION_REQUIRED_RESPONSE,
            }
        },
    }
    if create_examples:
        overrides["create"]["examples"] = create_examples
    return overrides


def document_user_owned_viewset(
    resource_plural: str,
    resource_singular: str,
    create_description: str,
    tag: str,
    action_overrides: dict[str, dict] | None = None,
):
    action_overrides = action_overrides or {}

    def schema(action: str, **kwargs):
        schema_kwargs = {"tags": [tag], **kwargs}
        action_override = action_overrides.get(action, {})
        override_responses = action_override.get("responses", {})
        if override_responses:
            responses = dict(schema_kwargs.get("responses", {}))
            responses.update(override_responses)
            schema_kwargs["responses"] = responses
        schema_kwargs.update({key: value for key, value in action_override.items() if key != "responses"})
        return extend_schema(**schema_kwargs)

    return extend_schema_view(
        list=schema(
            "list",
            summary=f"List {resource_plural}",
            description=f"Return all {resource_plural} owned by the authenticated user.",
        ),
        retrieve=schema(
            "retrieve",
            summary=f"Get {resource_singular}",
            description=f"Return a single {resource_singular} owned by the authenticated user.",
        ),
        create=schema(
            "create",
            summary=f"Create {resource_singular}",
            description=create_description,
        ),
        update=schema(
            "update",
            summary=f"Replace {resource_singular}",
            description=f"Replace an existing {resource_singular} owned by the authenticated user.",
        ),
        partial_update=schema(
            "partial_update",
            summary=f"Update {resource_singular}",
            description=f"Update one or more fields on an existing {resource_singular} owned by the authenticated user.",
        ),
        destroy=schema(
            "destroy",
            summary=f"Delete {resource_singular}",
            description=f"Delete an existing {resource_singular} owned by the authenticated user.",
        ),
    )


def document_tenant_owned_viewset(
    resource_plural: str,
    resource_singular: str,
    create_description: str,
    tag: str,
    action_overrides: dict[str, dict] | None = None,
):
    parameters = [TENANT_ID_PARAMETER]
    action_overrides = action_overrides or {}

    def schema(action: str, **kwargs):
        schema_kwargs = {"tags": [tag], **kwargs}
        action_override = action_overrides.get(action, {})
        override_responses = action_override.get("responses", {})
        if override_responses:
            responses = dict(schema_kwargs.get("responses", {}))
            responses.update(override_responses)
            schema_kwargs["responses"] = responses
        schema_kwargs.update({key: value for key, value in action_override.items() if key != "responses"})
        return extend_schema(**schema_kwargs)

    return extend_schema_view(
        list=schema(
            "list",
            summary=f"List {resource_plural}",
            description=f"Return all {resource_plural} for the selected tenant.",
            parameters=parameters,
        ),
        retrieve=schema(
            "retrieve",
            summary=f"Get {resource_singular}",
            description=f"Return a single {resource_singular} for the selected tenant.",
            parameters=parameters,
        ),
        create=schema(
            "create",
            summary=f"Create {resource_singular}",
            description=create_description,
            parameters=parameters,
        ),
        update=schema(
            "update",
            summary=f"Replace {resource_singular}",
            description=f"Replace an existing {resource_singular} for the selected tenant.",
            parameters=parameters,
        ),
        partial_update=schema(
            "partial_update",
            summary=f"Update {resource_singular}",
            description=f"Update one or more fields on an existing {resource_singular} for the selected tenant.",
            parameters=parameters,
        ),
        destroy=schema(
            "destroy",
            summary=f"Delete {resource_singular}",
            description=f"Delete an existing {resource_singular} for the selected tenant.",
            parameters=parameters,
        ),
    )


class TenantOwnedQuerysetMixin:
    queryset: Any = None

    def get_tenant(self):
        tenant_id = self.kwargs.get("tenant_id")
        if tenant_id is None:
            raise AssertionError("tenant_id must be present in nested tenant-scoped routes")
        try:
            return Tenant.objects.get(pk=tenant_id, user=self.request.user)
        except Tenant.DoesNotExist as exc:
            raise NotFound("Tenant not found.") from exc

    def get_queryset(self):
        queryset = self.queryset
        if queryset is None:
            raise AssertionError("queryset must be set on tenant-scoped viewsets")
        return queryset.filter(tenant=self.get_tenant())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = self.get_tenant()
        return context

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_tenant())



@document_user_owned_viewset(
    resource_plural="tenants",
    resource_singular="tenant",
    create_description="Create a new tenant for the authenticated user. The requesting user is attached automatically.",
    tag="Tenant Management",
    action_overrides=build_crud_action_overrides(
        TenantSerializer,
        resource_plural="tenants owned by the authenticated user",
        resource_singular="tenant",
        create_examples=[TENANT_CREATE_REQUEST_EXAMPLE, TENANT_RESPONSE_EXAMPLE],
        create_response_examples=[TENANT_RESPONSE_EXAMPLE],
        retrieve_examples=[TENANT_RESPONSE_EXAMPLE],
    ),
)
class TenantViewSet(viewsets.ModelViewSet):
    serializer_class = TenantSerializer
    queryset = Tenant.objects.select_related("user")
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@document_tenant_owned_viewset(
    resource_plural="tenant configurations",
    resource_singular="tenant configuration",
    create_description="Create a new tenant configuration record for the selected tenant, including authority weighting and decay settings.",
    tag="Tenant Management",
    action_overrides=build_crud_action_overrides(
        TenantConfigSerializer,
        resource_plural="tenant configurations for the selected tenant",
        resource_singular="tenant configuration",
    ),
)
class TenantConfigViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = TenantConfigSerializer
    queryset = TenantConfig.objects.select_related("tenant")


@document_tenant_owned_viewset(
    resource_plural="entities",
    resource_singular="entity",
    create_description="Create a new tracked entity for the selected tenant, such as a company, person, or project.",
    tag="Entity Catalog",
    action_overrides=build_crud_action_overrides(
        EntitySerializer,
        resource_plural="entities for the selected tenant",
        resource_singular="entity",
    ),
)
class EntityViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = EntitySerializer
    queryset = Entity.objects.select_related("tenant")


@document_tenant_owned_viewset(
    resource_plural="content items",
    resource_singular="content item",
    create_description="Create a new content item for the selected tenant. Any related entity must belong to the same tenant.",
    tag="Content Library",
    action_overrides=build_crud_action_overrides(
        ContentSerializer,
        resource_plural="content items for the selected tenant",
        resource_singular="content item",
        create_examples=[CONTENT_CREATE_REQUEST_EXAMPLE, CONTENT_RESPONSE_EXAMPLE],
        create_response_examples=[CONTENT_RESPONSE_EXAMPLE],
        retrieve_examples=[CONTENT_RESPONSE_EXAMPLE],
    ),
)
class ContentViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = ContentSerializer
    queryset = Content.objects.select_related("tenant", "entity")


@document_tenant_owned_viewset(
    resource_plural="skill results",
    resource_singular="skill result",
    create_description="Create a new skill result for tenant content. The referenced content must belong to the selected tenant.",
    tag="AI Processing",
    action_overrides=build_crud_action_overrides(
        SkillResultSerializer,
        resource_plural="skill results for the selected tenant",
        resource_singular="skill result",
        retrieve_examples=[SKILL_RESULT_RESPONSE_EXAMPLE],
    ),
)
class SkillResultViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = SkillResultSerializer
    queryset = SkillResult.objects.select_related("content", "tenant", "superseded_by")


@document_tenant_owned_viewset(
    resource_plural="user feedback entries",
    resource_singular="user feedback entry",
    create_description="Create a new feedback entry for content in the selected tenant. The authenticated user is recorded automatically.",
    tag="Feedback",
    action_overrides=build_crud_action_overrides(
        UserFeedbackSerializer,
        resource_plural="user feedback entries for the selected tenant",
        resource_singular="user feedback entry",
    ),
)
class UserFeedbackViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = UserFeedbackSerializer
    queryset = UserFeedback.objects.select_related("content", "tenant", "user")

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_tenant(), user=self.request.user)


@document_tenant_owned_viewset(
    resource_plural="ingestion runs",
    resource_singular="ingestion run",
    create_description="Create a new ingestion run record for the selected tenant to track a content ingestion attempt and its status.",
    tag="Ingestion",
    action_overrides=build_crud_action_overrides(
        IngestionRunSerializer,
        resource_plural="ingestion runs for the selected tenant",
        resource_singular="ingestion run",
    ),
)
class IngestionRunViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = IngestionRunSerializer
    queryset = IngestionRun.objects.select_related("tenant")


@document_tenant_owned_viewset(
    resource_plural="source configurations",
    resource_singular="source configuration",
    create_description="Create a new source configuration for the selected tenant. Plugin-specific configuration is validated before the record is saved.",
    tag="Ingestion",
    action_overrides=build_crud_action_overrides(
        SourceConfigSerializer,
        resource_plural="source configurations for the selected tenant",
        resource_singular="source configuration",
        create_examples=[
            SOURCE_CONFIG_CREATE_REQUEST_EXAMPLE,
            SOURCE_CONFIG_REDDIT_REQUEST_EXAMPLE,
            SOURCE_CONFIG_RESPONSE_EXAMPLE,
        ],
        create_response_examples=[SOURCE_CONFIG_RESPONSE_EXAMPLE],
        retrieve_examples=[SOURCE_CONFIG_RESPONSE_EXAMPLE],
    ),
)
class SourceConfigViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = SourceConfigSerializer
    queryset = SourceConfig.objects.select_related("tenant")


@document_tenant_owned_viewset(
    resource_plural="review queue entries",
    resource_singular="review queue entry",
    create_description="Create a new review queue entry for the selected tenant. The referenced content must belong to the same tenant.",
    tag="Review Queue",
    action_overrides=build_crud_action_overrides(
        ReviewQueueSerializer,
        resource_plural="review queue entries for the selected tenant",
        resource_singular="review queue entry",
    ),
)
class ReviewQueueViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = ReviewQueueSerializer
    queryset = ReviewQueue.objects.select_related("content", "tenant")
