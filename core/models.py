import secrets

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models


def generate_project_intake_token() -> str:
	return secrets.token_hex(16)


def generate_confirmation_token() -> str:
	return secrets.token_urlsafe(24)


class EntityType(models.TextChoices):
	INDIVIDUAL = "individual", "Individual"
	VENDOR = "vendor", "Vendor"
	ORGANIZATION = "organization", "Organization"


class SkillStatus(models.TextChoices):
	PENDING = "pending", "Pending"
	RUNNING = "running", "Running"
	COMPLETED = "completed", "Completed"
	FAILED = "failed", "Failed"


class FeedbackType(models.TextChoices):
	UPVOTE = "upvote", "Upvote"
	DOWNVOTE = "downvote", "Downvote"


class SourcePluginName(models.TextChoices):
	RSS = "rss", "RSS"
	REDDIT = "reddit", "Reddit"


class NewsletterIntakeStatus(models.TextChoices):
	PENDING = "pending", "Pending"
	EXTRACTED = "extracted", "Extracted"
	FAILED = "failed", "Failed"
	REJECTED = "rejected", "Rejected"


class RunStatus(models.TextChoices):
	RUNNING = "running", "Running"
	SUCCESS = "success", "Success"
	FAILED = "failed", "Failed"


class ReviewReason(models.TextChoices):
	LOW_CONFIDENCE_CLASSIFICATION = "low_confidence_classification", "Low Confidence Classification"
	BORDERLINE_RELEVANCE = "borderline_relevance", "Borderline Relevance"


class ReviewResolution(models.TextChoices):
	HUMAN_APPROVED = "human_approved", "Human Approved"
	HUMAN_REJECTED = "human_rejected", "Human Rejected"


class Project(models.Model):
	name = models.CharField(max_length=255)
	group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="projects")
	topic_description = models.TextField()
	content_retention_days = models.PositiveIntegerField(default=365)
	intake_token = models.CharField(max_length=64, unique=True, default=generate_project_intake_token, editable=False)
	intake_enabled = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["name"]

	def __str__(self) -> str:
		return self.name


class ProjectConfig(models.Model):
	project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="config")
	upvote_authority_weight = models.FloatField(default=0.1)
	downvote_authority_weight = models.FloatField(default=-0.05)
	authority_decay_rate = models.FloatField(default=0.95)

	class Meta:
		verbose_name = "Project config"
		verbose_name_plural = "Project configs"

	def __str__(self) -> str:
		return f"Config for {self.project.name}"


class Entity(models.Model):
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="entities")
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
			models.UniqueConstraint(fields=["project", "name"], name="core_entity_unique_project_name"),
		]

	def __str__(self) -> str:
		return self.name


class Content(models.Model):
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="contents")
	url = models.URLField()
	title = models.CharField(max_length=512)
	author = models.CharField(max_length=255, blank=True)
	entity = models.ForeignKey(Entity, null=True, blank=True, on_delete=models.SET_NULL, related_name="contents")
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
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="intake_allowlist")
	sender_email = models.EmailField()
	confirmed_at = models.DateTimeField(null=True, blank=True)
	confirmation_token = models.CharField(max_length=64, unique=True, default=generate_confirmation_token)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["sender_email"]
		constraints = [
			models.UniqueConstraint(fields=["project", "sender_email"], name="core_allowlist_unique_project_sender"),
		]

	def __str__(self) -> str:
		return f"{self.sender_email} for {self.project.name}"

	@property
	def is_confirmed(self) -> bool:
		return self.confirmed_at is not None


class NewsletterIntake(models.Model):
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="newsletter_intakes")
	sender_email = models.EmailField()
	subject = models.CharField(max_length=512)
	received_at = models.DateTimeField(auto_now_add=True)
	raw_html = models.TextField(blank=True)
	raw_text = models.TextField(blank=True)
	message_id = models.CharField(max_length=255, unique=True)
	status = models.CharField(max_length=16, choices=NewsletterIntakeStatus.choices, default=NewsletterIntakeStatus.PENDING)
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
	content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="skill_results")
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="skill_results")
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
	content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="feedback")
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="feedback")
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_feedback")
	feedback_type = models.CharField(max_length=16, choices=FeedbackType.choices)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]
		constraints = [
			models.UniqueConstraint(fields=["content", "user"], name="core_feedback_unique_content_user"),
		]

	def __str__(self) -> str:
		return f"{self.feedback_type} by {self.user}"


class SourceConfig(models.Model):
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="source_configs")
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
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="ingestion_runs")
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
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="review_queue_items")
	content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="review_queue_items")
	reason = models.CharField(max_length=64, choices=ReviewReason.choices)
	confidence = models.FloatField()
	created_at = models.DateTimeField(auto_now_add=True)
	resolved = models.BooleanField(default=False)
	resolution = models.CharField(max_length=64, choices=ReviewResolution.choices, blank=True)

	class Meta:
		ordering = ["resolved", "-created_at"]

	def __str__(self) -> str:
		return f"{self.reason} for {self.content.title}"
