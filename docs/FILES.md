# File Organization

In Django, you have one **project** (the container for your settings and main routing) and one or more **apps** (reusable modules that handle specific logic).

## File Breakdown: `newsletter_maker/` (The Project)

This is the "brain." It contains your global settings, main URL configuration, and WSGI/ASGI entry points for the server.

- **`settings.py`**: All configuration (Database URLs, installed apps, Celery broker settings).
- **`urls.py`**: The "main" URL file that imports the `api_urls.py` and `core.urls`.
- **`wsgi.py` / `asgi.py`**: The interface Gunicorn uses to run your app.
- **`celery.py`**: Where Celery is initialized for the project.

## File Breakdown: `core/` (The Application)

This is where the actual "features" live. Django encourages putting logic into apps so you could, in theory, pluck this `core` folder out and drop it into a different project.

- **`models.py`**: The most important file. It defines your database schema using Python classes.
- **`serializers.py`**: Part of **DRF** (Django REST Framework). It converts your `models.py` data into JSON for the API.
- **`tasks.py`**: Contains your **Celery** background tasks (e.g., the actual code that sends the newsletter).
- **`api.py` & `api_urls.py`**: These likely house your DRF logic (ViewSets) and the specific URL paths for your API endpoints.
- **`admin.py`**: Configures how your models look in the built-in Django `/admin` interface.
- **`views.py` & `urls.py`**: Handle standard web requests and map them to templates.
- **`embeddings.py`**: Likely a custom file for your specific app (given the `qdrant` service you have), probably handling Vector Search or AI logic.
- **`migrations/`**: A history of your database changes.
- **`templates/` & `static/`**: Your HTML files and CSS/JS/images.
- **`management/`**: Contains custom terminal commands (e.g., `python manage.py my_custom_command`).
- **`tests.py`**: Where your automated tests live.
