"""Core domain models for projects, ingestion, and editorial review.

The admin, API, Celery tasks, and AI pipeline all revolve around the models in this
module. Adding model-level docstrings here gives Django admindocs a useful summary
of the core entities new contributors interact with first.
"""

import base64
import hashlib
import secrets
from urllib.parse import urlsplit, urlunsplit

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models


def generate_project_intake_token() -> str:
    """Generate the stable token used in project-specific intake email aliases.

    Returns:
        A random hex token that can be embedded in addresses like
        ``intake+<token>@...`` to route inbound newsletters to a project.
    """

    return secrets.token_hex(16)


def generate_confirmation_token() -> str:
    """Generate a one-time token for newsletter sender confirmation links.

    Returns:
        A URL-safe random token stored on an allowlist entry until the sender
        confirms newsletter intake access.
    """

    return secrets.token_urlsafe(24)


def normalize_bluesky_handle(handle: str) -> str:
    """Normalize Bluesky handles so stored account references stay consistent."""

    return handle.strip().removeprefix("@").lower()


def normalize_bluesky_pds_url(pds_url: str) -> str:
    """Normalize a user-provided PDS URL to its base host form."""

    stripped_url = pds_url.strip().rstrip("/")
    if not stripped_url:
        return ""
    parsed_url = urlsplit(stripped_url)
    path = parsed_url.path.rstrip("/")
    if path.endswith("/xrpc"):
        path = path[: -len("/xrpc")]
    return urlunsplit(
        (parsed_url.scheme, parsed_url.netloc, path, parsed_url.query, parsed_url.fragment)
    ).rstrip("/")


def _bluesky_credentials_fernet() -> Fernet:
    """Build the symmetric cipher used for Bluesky app-password storage."""

    key_material = (
        getattr(settings, "BLUESKY_CREDENTIALS_ENCRYPTION_KEY", "")
        or settings.SECRET_KEY
    )
    derived_key = base64.urlsafe_b64encode(
        hashlib.sha256(key_material.encode("utf-8")).digest()
    )
    return Fernet(derived_key)


class EntityType(models.TextChoices):
    """Supported types of tracked entities within a project."""

    INDIVIDUAL = "individual", "Individual"
    VENDOR = "vendor", "Vendor"
    ORGANIZATION = "organization", "Organization"


class SkillStatus(models.TextChoices):
    """Execution states recorded for AI skill runs."""

    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class FeedbackType(models.TextChoices):
    """Editorial feedback signals that tune authority and ranking."""

    UPVOTE = "upvote", "Upvote"
    DOWNVOTE = "downvote", "Downvote"


class SourcePluginName(models.TextChoices):
    """Built-in ingestion plugins that can populate project content."""

    RSS = "rss", "RSS"
    REDDIT = "reddit", "Reddit"
    BLUESKY = "bluesky", "Bluesky"


class NewsletterIntakeStatus(models.TextChoices):
    """Lifecycle states for a raw inbound newsletter email."""

    PENDING = "pending", "Pending"
    EXTRACTED = "extracted", "Extracted"
    FAILED = "failed", "Failed"
    REJECTED = "rejected", "Rejected"


class RunStatus(models.TextChoices):
    """Outcome states for ingestion runs."""

    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class ReviewReason(models.TextChoices):
    """Reasons content is pushed to the manual review queue."""

    LOW_CONFIDENCE_CLASSIFICATION = (
        "low_confidence_classification",
        "Low Confidence Classification",
    )
    BORDERLINE_RELEVANCE = "borderline_relevance", "Borderline Relevance"


class ReviewResolution(models.TextChoices):
    """Human outcomes for review queue items."""

    HUMAN_APPROVED = "human_approved", "Human Approved"
    HUMAN_REJECTED = "human_rejected", "Human Rejected"


class Project(models.Model):
    """Represents a newsletter workspace owned by a Django auth group.

    A project defines the editorial topic, retention policy, and email-intake
    identity used by all downstream ingestion, relevance scoring, and review flows.
    Most other core models are scoped to a single project.
    """

    name = models.CharField(max_length=255)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="projects")
    topic_description = models.TextField()
    content_retention_days = models.PositiveIntegerField(default=365)
    intake_token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_project_intake_token,
        editable=False,
    )
    intake_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class BlueskyCredentials(models.Model):
    """Stores the authenticated Bluesky account used by one project.

    The plugin can read public content through AppView without credentials, but a
    stored account enables authenticated reads and self-hosted PDS support.
    """

    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name="bluesky_credentials"
    )
    handle = models.CharField(max_length=255)
    app_password_encrypted = models.TextField(blank=True)
    pds_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__name"]
        verbose_name_plural = "Bluesky credentials"

    def __str__(self) -> str:
        return f"Bluesky credentials for {self.project.name}"

    @property
    def client_base_url(self) -> str:
        """Return the effective base URL used by the ATProto client."""

        if not self.pds_url:
            return "https://bsky.social/xrpc"
        return f"{self.pds_url.rstrip('/')}/xrpc"

    def has_app_password(self) -> bool:
        """Return whether an encrypted app password has been stored."""

        return bool(self.app_password_encrypted)

    def has_stored_credential(self) -> bool:
        """Return whether an encrypted Bluesky credential has been stored."""

        return self.has_app_password()

    def set_app_password(self, app_password: str) -> None:
        """Encrypt and store the given Bluesky app password."""

        if not app_password:
            self.app_password_encrypted = ""
            return
        self.app_password_encrypted = _bluesky_credentials_fernet().encrypt(
            app_password.encode("utf-8")
        ).decode("utf-8")

    def set_stored_credential(self, credential_value: str) -> None:
        """Encrypt and store the given Bluesky credential value."""

        self.set_app_password(credential_value)

    def get_app_password(self) -> str:
        """Decrypt and return the stored Bluesky app password."""

        if not self.app_password_encrypted:
            return ""
        return _bluesky_credentials_fernet().decrypt(
            self.app_password_encrypted.encode("utf-8")
        ).decode("utf-8")

    def get_stored_credential(self) -> str:
        """Decrypt and return the stored Bluesky credential value."""

        return self.get_app_password()

    def save(self, *args, **kwargs):
        """Normalize stored account fields before persisting the credentials."""

        self.handle = normalize_bluesky_handle(self.handle)
        self.pds_url = normalize_bluesky_pds_url(self.pds_url)
        super().save(*args, **kwargs)


class ProjectConfig(models.Model):
    """Stores tunable scoring parameters for a single project.

    These values let the application adjust how strongly upvotes, downvotes, and
    score decay influence entity authority over time without changing code.
    """

    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name="config"
    )
    upvote_authority_weight = models.FloatField(default=0.1)
    downvote_authority_weight = models.FloatField(default=-0.05)
    authority_decay_rate = models.FloatField(default=0.95)

    class Meta:
        verbose_name = "Project config"
        verbose_name_plural = "Project configs"

    def __str__(self) -> str:
        return f"Config for {self.project.name}"


class Entity(models.Model):
    """Represents a person, vendor, or organization tracked inside a project.

    Content can optionally link to an entity so authority signals and editorial
    curation can accumulate around a known subject instead of isolated articles.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="entities"
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=32, choices=EntityType.choices)
    description = models.TextField(blank=True)
    authority_score = models.FloatField(default=0.5)
    website_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    bluesky_handle = models.CharField(max_length=255, blank=True)
    mastodon_handle = models.CharField(max_length=255, blank=True)
    twitter_handle = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"], name="core_entity_unique_project_name"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Content(models.Model):
    """Stores an ingested content item that may appear in a newsletter.

    A content row is the canonical record for fetched articles, newsletter links,
    or other source items. It keeps the raw text used for embedding, skill output,
    and editorial review, and it also links the row to its Qdrant vector via
    ``embedding_id``.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="contents"
    )
    url = models.URLField()
    title = models.CharField(max_length=512)
    author = models.CharField(max_length=255, blank=True)
    entity = models.ForeignKey(
        Entity,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contents",
    )
    source_plugin = models.CharField(max_length=64)
    content_type = models.CharField(max_length=64, blank=True)
    published_date = models.DateTimeField()
    ingested_at = models.DateTimeField(auto_now_add=True)
    content_text = models.TextField()
    relevance_score = models.FloatField(null=True, blank=True)
    embedding_id = models.CharField(max_length=64, blank=True)
    source_metadata = models.JSONField(default=dict, blank=True)
    is_reference = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-published_date"]
        indexes = [
            models.Index(fields=["project", "-published_date"]),
            models.Index(fields=["project", "-relevance_score"]),
            models.Index(fields=["project", "is_reference"]),
            models.Index(fields=["url"]),
        ]

    def __str__(self) -> str:
        return self.title


class IntakeAllowlist(models.Model):
    """Tracks who is allowed to send newsletters into a project inbox.

    When the first message arrives from a sender, the system creates an allowlist
    entry and emails a confirmation link. After confirmation, future inbound
    messages from the same sender can be processed automatically.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="intake_allowlist"
    )
    sender_email = models.EmailField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmation_token = models.CharField(
        max_length=64, unique=True, default=generate_confirmation_token
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sender_email"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "sender_email"],
                name="core_allowlist_unique_project_sender",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sender_email} for {self.project.name}"

    @property
    def is_confirmed(self) -> bool:
        """Return whether the sender has confirmed newsletter intake access."""

        return self.confirmed_at is not None


class NewsletterIntake(models.Model):
    """Stores a raw inbound newsletter email before extraction.

    Intake rows preserve the original email payload, deduplicate by message ID,
    and record whether extraction succeeded so the system can reprocess or audit
    inbound newsletter handling later.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="newsletter_intakes"
    )
    sender_email = models.EmailField()
    subject = models.CharField(max_length=512)
    received_at = models.DateTimeField(auto_now_add=True)
    raw_html = models.TextField(blank=True)
    raw_text = models.TextField(blank=True)
    message_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=16,
        choices=NewsletterIntakeStatus.choices,
        default=NewsletterIntakeStatus.PENDING,
    )
    extraction_result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["project", "sender_email", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.subject or self.message_id}"


class SkillResult(models.Model):
    """Persists the output of one AI skill execution for a content item.

    Skill results provide an auditable history of classifications, relevance
    scores, summaries, and related-content lookups, including model metadata,
    latency, and any superseded reruns.
    """

    content = models.ForeignKey(
        Content, on_delete=models.CASCADE, related_name="skill_results"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="skill_results"
    )
    skill_name = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=SkillStatus.choices)
    result_data = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    model_used = models.CharField(max_length=64, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    superseded_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supersedes",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content", "skill_name"]),
            models.Index(fields=["project", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.skill_name} for {self.content.title}"


class UserFeedback(models.Model):
    """Records an editor's feedback on a specific content item.

    Feedback is stored separately from the content row so the application can use
    it as an explicit human signal when adjusting ranking and authority logic.
    """

    content = models.ForeignKey(
        Content, on_delete=models.CASCADE, related_name="feedback"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="feedback"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="content_feedback",
    )
    feedback_type = models.CharField(max_length=16, choices=FeedbackType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["content", "user"], name="core_feedback_unique_content_user"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.feedback_type} by {self.user}"


class SourceConfig(models.Model):
    """Configures one ingestion source for a project.

    Each source config selects a plugin, stores its provider-specific settings,
    and records the last successful fetch time used for incremental ingestion.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="source_configs"
    )
    plugin_name = models.CharField(max_length=64, choices=SourcePluginName.choices)
    config = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    last_fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["plugin_name", "id"]
        indexes = [
            models.Index(fields=["project", "plugin_name", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.plugin_name} source for {self.project.name}"


class IngestionRun(models.Model):
    """Captures the outcome of one source-ingestion execution.

    Run rows make ingestion observable in the admin by recording the source,
    timestamps, item counts, and any error that stopped the fetch.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="ingestion_runs"
    )
    plugin_name = models.CharField(max_length=64)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=RunStatus.choices)
    items_fetched = models.IntegerField(default=0)
    items_ingested = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["project", "plugin_name", "-started_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.plugin_name} for {self.project.name}"


class ReviewQueue(models.Model):
    """Tracks content items that require a human decision.

    The AI pipeline adds rows here when classification confidence is low or the
    relevance score is borderline. Review outcomes are stored on the queue item so
    editors can see why an article was escalated and how it was resolved.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="review_queue_items"
    )
    content = models.ForeignKey(
        Content, on_delete=models.CASCADE, related_name="review_queue_items"
    )
    reason = models.CharField(max_length=64, choices=ReviewReason.choices)
    confidence = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolution = models.CharField(
        max_length=64, choices=ReviewResolution.choices, blank=True
    )

    class Meta:
        ordering = ["resolved", "-created_at"]

    def __str__(self) -> str:
        return f"{self.reason} for {self.content.title}"
