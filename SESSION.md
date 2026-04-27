# Session Restore Point



## Useful Commands From Today

```bash
docker run --rm newsletter-maker-app:dev python -c "import drf_standardized_errors; print('ok')"
docker compose exec django python -c "import drf_standardized_errors; print('ok')"
docker compose exec django pip show drf-standardized-errors
docker inspect newsletter-maker-django-1 --format '{{.Id}} {{.Image}} {{.Config.Image}}'
docker inspect newsletter-maker-django-1 --format '{{json .Mounts}}'
pytest core/tests/test_embeddings.py -q
ruff check core/management/commands/seed_demo.py core/tests/test_embeddings.py
```

