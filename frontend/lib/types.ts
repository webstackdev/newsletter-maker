export type Tenant = {
  id: number;
  name: string;
  user: number;
  topic_description: string;
  content_retention_days: number;
  created_at: string;
};

export type Entity = {
  id: number;
  tenant: number;
  name: string;
  type: "individual" | "vendor" | "organization";
  description: string;
  authority_score: number;
  website_url: string;
  github_url: string;
  linkedin_url: string;
  bluesky_handle: string;
  mastodon_handle: string;
  twitter_handle: string;
  created_at: string;
};

export type Content = {
  id: number;
  tenant: number;
  url: string;
  title: string;
  author: string;
  entity: number | null;
  source_plugin: string;
  content_type: string;
  published_date: string;
  ingested_at: string;
  content_text: string;
  relevance_score: number | null;
  embedding_id: string;
  is_reference: boolean;
  is_active: boolean;
};

export type SkillResult = {
  id: number;
  content: number;
  tenant: number;
  skill_name: string;
  status: "pending" | "running" | "completed" | "failed";
  result_data: Record<string, unknown> | null;
  error_message: string;
  model_used: string;
  latency_ms: number | null;
  confidence: number | null;
  created_at: string;
  superseded_by: number | null;
};

export type ReviewQueueItem = {
  id: number;
  tenant: number;
  content: number;
  reason: "low_confidence_classification" | "borderline_relevance";
  confidence: number;
  created_at: string;
  resolved: boolean;
  resolution: "human_approved" | "human_rejected" | "";
};

export type IngestionRun = {
  id: number;
  tenant: number;
  plugin_name: string;
  started_at: string;
  completed_at: string | null;
  status: "running" | "success" | "failed";
  items_fetched: number;
  items_ingested: number;
  error_message: string;
};

export type SourceConfig = {
  id: number;
  tenant: number;
  plugin_name: "rss" | "reddit";
  config: Record<string, unknown>;
  is_active: boolean;
  last_fetched_at: string | null;
};

export type UserFeedback = {
  id: number;
  content: number;
  tenant: number;
  user: number;
  feedback_type: "upvote" | "downvote";
  created_at: string;
};

export type HealthStatus = "healthy" | "degraded" | "failing" | "idle";

export type ContentSkillName = "content_classification" | "relevance_scoring" | "summarization" | "find_related";