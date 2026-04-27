import os
import sys
from pathlib import Path

import dj_database_url
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

if "pytest" in sys.modules:
    load_dotenv(BASE_DIR / ".env.test", override=True)

load_dotenv(BASE_DIR / ".env")

# Helpers: environment variables always arrive as strings. These helpers coerce
# common boolean and comma-separated list values into the Python types Django
# actually expects.
def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


# Fallback: this default keeps local development bootable even if .env has not
# been created yet. Production should still provide a real secret.
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key")
DEBUG = env_bool("DEBUG", default=True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", default="localhost,127.0.0.1")

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost,http://127.0.0.1,http://localhost:8080,http://127.0.0.1:8080",
)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "newsletter-maker/0.1")

INSTALLED_APPS = [
    "unfold",  # Must be first
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "core",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "import_export",
    "rest_framework",
    "drf_spectacular",
    "drf_standardized_errors",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "newsletter_maker.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "newsletter_maker.wsgi.application"

DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# DRF: the API defaults to authenticated access so browser sessions and basic
# auth work locally, but anonymous requests are rejected.
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_standardized_errors.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
}

DRF_STANDARDIZED_ERRORS = {
    "ALLOWED_ERROR_STATUS_CODES": ["400", "403", "404"],
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Unfold Admin Template
UNFOLD = {
    "SITE_TITLE": _("Newsletter Maker"),
    "SITE_HEADER": _("Newsletter Maker"),
    "SITE_SUBHEADER": _("Administration"),
    "SHOW_HISTORY": True,
    "DASHBOARD_CALLBACK": "core.utils.dashboard_callback",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/x-icon",
            "href": lambda request: static("core/favicon.ico"),
        },
    ],
    "SITE_ICON": lambda request: static("core/logo.png"),
    "SITE_SYMBOL": "speed", # Material Icon for the sidebar
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "500": "168 85 247",
            "900": "88 28 135",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
    },
}

# Add metadata for Swagger UI
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
