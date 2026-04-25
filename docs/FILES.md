# File Organization

In Django, you have one **project** (the container for your settings and main routing) and one or more **apps** (reusable modules that handle specific logic).

## File Breakdown: `newsletter_maker/` (The Project)

This is the "brain." It contains your global settings, main URL configuration, and WSGI/ASGI entry points for the server.

- **`settings.py`**: All configuration (Database URLs, installed apps, Celery broker settings).
- **`urls.py`**: The "main" URL file that imports the `api_urls.py` and `core.urls`.
- **`wsgi.py` / `asgi.py`**: The interface Gunicorn uses to run your app.
- **`celery.py`**: Where Celery is initialized for the project.

## File Breakdown: `core/` (The Application)

This is where the actual "features" live. Django encourages putting logic into apps so you could, in theory, pluck this `core` folder out and drop it into a different project. The `core` name is a popular label for the app that houses "base" functionality—like custom user models, global tasks, or shared logic—that doesn't fit neatly into a more specific feature name.

- **`models.py`**: The most important file. It defines your database schema using Python classes.
- **`serializers.py`**: Part of **DRF** (Django REST Framework). It converts your `models.py` data into JSON for the API.
- **`tasks.py`**: Contains your **Celery** background tasks (e.g., the actual code that sends the newsletter).
- **`api.py`**: This file DRF logic contains **ViewSets** or **Views**. It defines the behavior of the API—such as how it queries the database, applies permissions, and uses serializers to format data.
- **`api_urls.py`**: : This file contains the URL patterns specific to your API. It maps the incoming URL paths (like `/api/v1/newsletter/`) to the logic defined in `api.py`.
- **`admin.py`**: Configures how your models look in the built-in Django `/admin` interface.
- **`views.py` & `urls.py`**: Handle standard web requests and map them to templates.
- **`embeddings.py`**: Likely a custom file for your specific app (given the `qdrant` service you have), probably handling Vector Search or AI logic.
- **`migrations/`**: A history of your database changes.
- **`templates/` & `static/`**: Your HTML files and CSS/JS/images.
- **`management/`**: Contains custom terminal commands (e.g., `python manage.py my_custom_command`).
- **`tests.py`**: Where your automated tests live.

## Simplifying `api.py`

Your file is quite long because you are manually mapping 8 different ViewSets. If you want to keep the **Nested URL** structure (`/tenants/1/entities/`) but use a Router to save space, the most popular tool is a library called **`drf-nested-routers`**. This loses the benefit of seeing endpoints at a glance.

```python
# With drf-nested-routers (Simplified concept)
tenant_router = NestedSimpleRouter(router, r'tenants', lookup='tenant')
tenant_router.register(r'entities', EntityViewSet, basename='tenant-entities')
```

### API Documentation (The Professional Way)

What is the actual endpoint for `router.register("tenants", ...)`?

The `DefaultRouter` generates two main URL patterns for every registered string:

1. **The List View**: `/api/v1/tenants/`
   - Maps to `GET` (list) and `POST` (create).
2. **The Detail View**: `/api/v1/tenants/<pk>/`
   - Maps to `GET` (retrieve), `PUT` (update), `PATCH`, and `DELETE`.

Because you used `DefaultRouter`, it also adds a **Root View** at `/api/v1/` that acts as a directory for all your registered endpoints.

For larger projects, developers use **drf-spectacular** to automatically generate a **Swagger** or **Redoc** page (usually at `/api/docs/`).

This creates a beautiful, interactive documentation site that shows every endpoint, the required parameters (like `tenant_id`), and the expected JSON format.

**Step 1: Install the Package**

First, install the library and its optional dependencies for the Swagger UI. Since you are using Docker, you can run this command to install it temporarily or add it to your `requirements.txt`:

```bash
docker exec -it newsletter-maker-django-1 pip install drf-spectacular
```

**Step 2: Update `settings.py`**

You need to register the app and tell DRF to use Spectacular's schema generator.

```python
INSTALLED_APPS = [
    # ...
    'drf_spectacular',
]

REST_FRAMEWORK = {
    # ...
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# Optional: Add metadata for your Swagger UI
SPECTACULAR_SETTINGS = {
    'TITLE': 'Newsletter Maker API',
    'DESCRIPTION': 'API documentation for the newsletter maker app',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
```

**Step 3: Add the Swagger URLs**

In your **`newsletter_maker/urls.py`** (the project root URL file), add the paths to serve the schema and the UI.

```python
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # ... existing paths
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # This is the actual Swagger page
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
```

**How to Access It**

Once you save the files and the server restarts:

1. Navigate to `http://localhost:8000/api/docs/` in your browser.
2. You will see a live, interactive list of all your endpoints, including your **Tenants**, **Entities**, and **Review Queue**.
3. You can even click **"Try it out"** on any endpoint to send real requests directly from the documentation.

Why use this over `show_urls`?

- **Interactivity**: You can test endpoints with real data without needing a tool like Postman.
- **Model Schemas**: It shows exactly what JSON structure your serializers expect and return.
- **Documentation**: You can add human-readable descriptions to your endpoints using Python docstrings in your `api.py`.

To enhance your Swagger UI with clear descriptions and examples, you use decorators provided by `drf-spectacular`. This allows you to document what each endpoint does and what the data should look like without changing your actual business logic.

**Documenting ViewSet Actions**

Because your `ViewSets` (like `TenantViewSet`) provide multiple actions (list, create, etc.) in one class, you use the `@extend_schema_view` decorator to target each action individually. 

**Example for your `TenantViewSet` in `api.py`:**

```python
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample

@extend_schema_view(
    list=extend_schema(
        summary="List all tenants",
        description="Returns a full list of all tenants registered in the system.",
    ),
    retrieve=extend_schema(
        summary="Get tenant details",
        description="Returns the detailed configuration and status for a single tenant.",
        examples=[
            OpenApiExample(
                'Example Tenant Response',
                value={
                    "id": 1,
                    "name": "Acme Corp",
                    "slug": "acme-corp",
                    "status": "active"
                }
            )
        ]
    )
)
class TenantViewSet(viewsets.ModelViewSet):
    # ... your existing code
```

**2. Adding Parameter Descriptions**

For your nested URLs (like `/tenants/<int:tenant_id>/entities/`), you can explicitly describe what the `tenant_id` is for so it shows up in the Swagger "Parameters" section.

```python
from drf_spectacular.utils import OpenApiParameter

@extend_schema(
    parameters=[
        OpenApiParameter(
            name='tenant_id', 
            type=int, 
            location=OpenApiParameter.PATH, 
            description='The unique ID of the parent tenant'
        ),
    ],
    description="Retrieve all entities belonging to a specific tenant."
)
def list(self, request, *args, **kwargs):
    return super().list(request, *args, **kwargs)
```

**3. Using Docstrings for "Auto-Docs" **

If you want a simpler approach, `drf-spectacular` automatically picks up standard Python **docstrings** from your methods and uses them as descriptions in the Swagger UI.

```python
def create(self, request, *args, **kwargs):
    """
    Create a new newsletter source configuration.
    
    This endpoint validates the RSS/Atom feed URL before saving.
    """
    return super().create(request, *args, **kwargs)
```

**4. Grouping with Tags**

You can group your endpoints into logical sections (e.g., "Management", "Ingestion", "AI") using the `tags` parameter. This makes a long list of endpoints much easier to navigate in the browser.

```python
@extend_schema(tags=['Tenant Management'])
class TenantViewSet(viewsets.ModelViewSet):
    # ...
```

**Summary of Key Tools**

- **`@extend_schema_view`**: Used on the class to document multiple actions at once.
- **`@extend_schema`**: Used on a single method for deep customization.
- **`OpenApiExample`**: Used to show users exactly what a sample JSON request or response looks like.

To add custom validation that is both functional and documented in Swagger, you must override the `get_queryset` method or specific action methods in your `api.py` and then use `responses` in your `@extend_schema` decorator.

**1. The Code: Custom 404 Validation**

You can use `get_object_or_404` to ensure a tenant exists before allowing access to related data. In **DRF**, this automatically raises an `Http404` exception, which the framework translates into a clean JSON error response.

**Example in `core/api.py`:**

```python
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from .models import Tenant, Entity

class EntityViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        # Captures 'tenant_id' from the URL we defined earlier
        tenant_id = self.kwargs.get("tenant_id")
        
        # This will raise a 404 if the tenant doesn't exist
        tenant = get_object_or_404(Tenant, id=tenant_id)
        
        # If tenant exists, return only their entities
        return Entity.objects.filter(tenant=tenant)
```

**2. The Documentation: Custom 404 Responses**

To make this "Tenant Not Found" error visible in Swagger, you update your `@extend_schema` to include a **404 response**.

```python
from drf_spectacular.utils import extend_schema, OpenApiResponse

@extend_schema(
    summary="List tenant entities",
    responses={
        200: EntitySerializer(many=True),
        404: OpenApiResponse(
            description="Tenant not found",
            # This shows the exact JSON the user will receive
            examples=[
                OpenApiExample(
                    "Standard 404",
                    value={"detail": "No Tenant matches the given query."}
                )
            ]
        ),
    }
)
def list(self, request, *args, **kwargs):
    return super().list(request, *args, **kwargs)
```

**Why this is better than built-in validation:**

- **Security**: It prevents users from "guessing" if a tenant exists by returning a 404 for non-existent tenants instead of an empty list `[]`.
- **Explicit Docs**: By defining `responses={404: ...}`, a new red "404" row appears in your Swagger UI, telling API consumers exactly what to expect if they use an invalid `tenant_id`.
- **Cleaner Logs**: Since `get_object_or_404` is a standard exception, your **Structlog** [turn 17] will capture it correctly without extra boilerplate code.

Using the drf-standardized-errors package is the professional way to clean up your API's error responses and automatically document them in Swagger. It replaces Django REST Framework's default, sometimes inconsistent error formats with a single, structured JSON format. 

**1. Install and Configure**

First, install the package with the OpenAPI support extension:

```bash
docker exec -it newsletter-maker-django-1 pip install "drf-standardized-errors[openapi]"
```

Then, update your **`settings.py`** to tell DRF to use this new handler:

```python
INSTALLED_APPS = [
    # ...
    "drf_standardized_errors",
]

REST_FRAMEWORK = {
    # ...
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
}
```

**2. Automatic Documentation**

Once registered, this package works with [drf-spectacular](https://drf-spectacular.readthedocs.io/) to automatically inject standardized error schemas (like 400, 401, and 404) into every endpoint in your Swagger UI. You no longer need to manually add `@extend_schema(responses={404: ...})` to every single view.

**3. Standardized Error Format**

Before this package, DRF might return different shapes for different errors. Now, every error (including those from your `get_object_or_404` call) will look like this:

```json
{
  "errors": [
    {
      "status": 404,
      "code": "not_found",
      "detail": "The requested resource was not found."
    }
  ]
}
```

This predictability is a massive benefit for frontend developers who need to write consistent error-handling logic in their code.

**4. Customizing the Global Schema**

If you find that standard 404 errors are cluttering every single endpoint in your docs (like your `list` views where a 404 is unlikely), you can configure drf-spectacular settings or the standardized errors settings to **hide certain error types** by default.

## `api.py`

This code is a sophisticated example of **Multi-Tenancy** and **Security**. Its primary goal is to ensure that users can only see and modify data belonging to a **Tenant** they own.

Here is the breakdown of the two main strategies used:

**The `TenantOwnedQuerysetMixin`**

This is a reusable "plugin" (Mixin) that handles all the security logic for resources nested under a tenant (like `/tenants/1/entities/`).

- **`get_tenant()`**: This is the gatekeeper. It looks at the URL for `tenant_id` and checks if the current user (`self.request.user`) actually owns that tenant. If they don't, it throws a `NotFound` error (404), preventing users from "snooping" on other people's tenant IDs.
- **`get_queryset()`**: Instead of showing every `Entity` in the database, it calls `filter(tenant=...)`. This ensures that even if a user manages to hit a "list" endpoint, they only see the data linked to the tenant validated in the step above.
- **`get_serializer_context()`**: It passes the `tenant` object into the Serializer. This is helpful if your serializer needs to do specific validation based on tenant settings.
- **`perform_create()`**: When you save a new object (like a new `Entity`), it **automatically attaches the tenant** to that object. The frontend doesn't need to send the tenant ID in the JSON body because the Mixin "injects" it from the URL.

**The `TenantViewSet`**

This manages the "Parent" objects.

- **`select_related("user")`**: This is a performance optimization. It tells Django to join the User table in the SQL query so it doesn't have to make a separate database trip for every tenant in a list.
- **Ownership Check**: The `get_queryset` here filters by `user=self.request.user`, meaning when you visit `/api/v1/tenants/`, you only see *your* companies/tenants.

**The ViewSets (The Implementation)**

Notice how `TenantConfigViewSet`, `EntityViewSet`, etc., all inherit from `TenantOwnedQuerysetMixin`.

- By simply adding that Mixin to the class definition, all 8 of those ViewSets instantly gain **automatic filtering**, **nested URL support**, and **security validation** without you having to rewrite that logic 8 times.
- **`select_related` everywhere**: The author is very careful with performance. For example, `ContentViewSet` joins `tenant` AND `entity`, which prevents the "N+1 query problem" (where the database gets hammered with tiny individual requests).

**Special Case: `UserFeedbackViewSet`**

Notice it overrides `perform_create`:

```python
def perform_create(self, serializer):
    serializer.save(tenant=self.get_tenant(), user=self.request.user)
```

This ensures that when feedback is submitted, the system automatically records **which tenant** it belongs to AND **which user** wrote it, pulled directly from the session/token.

**Summary**

This is **very high-quality Django code**. It uses the "Don't Repeat Yourself" (DRY) principle to enforce a strict security boundary. No matter which endpoint you hit, the system verifies your identity and your relationship to the data before showing a single row.

Would you like to see how the **Serializers** use that `context["tenant"]` we added in the Mixin?**

## Improving Tests

### Console Capture

Using `capsys` from pytest and pytest-mock cleans up testing console output.

Before:

```python
@patch("core.management.commands.embedding_smoke.upsert_content_embedding", return_value="embedding-123")
def test_embedding_smoke_command_can_upsert_content(self, upsert_mock):
    with patch("sys.stdout") as stdout_mock:
        call_command("embedding_smoke", content_id=self.content.id)
    upsert_mock.assert_called_once()     written_output = "".join(call.args[0] for call in stdout_mock.write.call_args_list if call.args)
    self.assertIn("embedding-123", written_output)
```

After:

```python
def test_embedding_smoke_command_can_upsert_content(mocker, capsys, db):
    # 1. Patch the embedding function
    mock_upsert = mocker.patch(
        "core.management.commands.embedding_smoke.upsert_content_embedding", 
        return_value="embedding-123"
    )

    # 2. Run the command (no 'with' block needed)
    call_command("embedding_smoke", content_id=1)

    # 3. Use capsys to read the output
    captured = capsys.readouterr()
    
    # 4. Assertions
    mock_upsert.assert_called_once()
    assert "embedding-123" in captured.out
```

## Test Env Vars

`pytest-django` lets you do this to override Django settings, before:

```python
@override_settings(
    EMBEDDING_PROVIDER="openrouter",
    EMBEDDING_MODEL="openai/text-embedding-3-small",
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_BASE="https://openrouter.ai/api/v1",
    OPENROUTER_APP_NAME="newsletter-maker",
)
@patch("core.embeddings.httpx.post")
def test_openrouter_embedding_provider_calls_embeddings_endpoint(self, post_mock):
    post_mock.return_value = SimpleNamespace(
        json=lambda: {"data": [{"embedding": [0.5, 0.6]}]},
        raise_for_status=lambda: None,
    )

    vector = embeddings.embed_text("api text")

    self.assertEqual(vector, [0.5, 0.6])
    self.assertIn("/embeddings", post_mock.call_args.args[0])
    self.assertEqual(post_mock.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")
```

Use a `.env.test` file, with a `conftest.py` file in the project root:

```python
# conftest.py
import os
from dotenv import load_dotenv

def pytest_configure():
    """
    This runs before any tests (and before Django setup).
    It loads the .env.test file into the environment.
    """
    load_dotenv(".env.test")
```
