SPECTACULAR_SETTINGS = {
    "TITLE": "Newsletter Maker API",
    "DESCRIPTION": "API documentation for the newsletter maker app",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "POSTPROCESSING_HOOKS": ["drf_standardized_errors.openapi_hooks.postprocess_schema_enums"],
    "ENUM_NAME_OVERRIDES": {
        "ValidationErrorEnum": "drf_standardized_errors.openapi_serializers.ValidationErrorEnum.choices",
        "ClientErrorEnum": "drf_standardized_errors.openapi_serializers.ClientErrorEnum.choices",
        "ServerErrorEnum": "drf_standardized_errors.openapi_serializers.ServerErrorEnum.choices",
        "ParseErrorCodeEnum": "drf_standardized_errors.openapi_serializers.ParseErrorCodeEnum.choices",
        "ErrorCode403Enum": "drf_standardized_errors.openapi_serializers.ErrorCode403Enum.choices",
        "ErrorCode404Enum": "drf_standardized_errors.openapi_serializers.ErrorCode404Enum.choices",
    },
    "TAGS": [
        {
            "name": "Tenant Management",
            "description": "Create tenants and manage tenant-specific configuration for newsletter workspaces.",
        },
        {
            "name": "Entity Catalog",
            "description": "Manage tracked people, companies, and organizations associated with a tenant.",
        },
        {
            "name": "Content Library",
            "description": "Browse and maintain ingested content items that feed newsletter generation and ranking.",
        },
        {
            "name": "AI Processing",
            "description": "Inspect AI skill execution results, model outputs, and confidence metadata for tenant content.",
        },
        {
            "name": "Feedback",
            "description": "Capture editorial feedback signals that influence ranking and future recommendation quality.",
        },
        {
            "name": "Ingestion",
            "description": "Configure source plugins and review ingestion runs for each tenant.",
        },
        {
            "name": "Review Queue",
            "description": "Review borderline or low-confidence content items that need human resolution.",
        },
    ],
}
