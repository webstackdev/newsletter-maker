# Session Restore Point

## Date

- 2026-04-27

## What Was Completed

- Implemented WP7 demo seeding in `core/management/commands/seed_demo.py`.
- `seed_demo` now creates deterministic offline demo data instead of depending on live Reddit/RSS/LLM calls.
- Seeded dataset shape:
  - 1 demo tenant: `Platform Engineering Weekly`
  - 15 entities
  - 8 source configs
  - 50 reference corpus items
  - 200 demo content items
  - 515 skill results total
  - review queue items
  - 45 feedback rows
  - 6 ingestion runs
- Added resilience in `seed_demo` so embedding sync warns and stops cleanly if vector/embedding infrastructure is unavailable.
- Changed `justfile` so `seed` now runs inside the live Django container:
  - `docker compose exec django python manage.py seed_demo`

## Tests / Validation That Passed

- `pytest core/tests/test_embeddings.py -q`
  - Final status before stopping: `15 passed`
- `ruff check core/management/commands/seed_demo.py core/tests/test_embeddings.py`
  - Passed
- `just --list`
  - Passed after `justfile` changes

## Current Blocker

`just seed` still fails inside the running Django container because Django cannot import `drf_standardized_errors`.

Exact failure inside the live service container:

```bash
docker compose exec django python -c "import drf_standardized_errors; print('ok')"
```

Result:

```text
ModuleNotFoundError: No module named 'drf_standardized_errors'
```

## Important Verified Facts

1. The dependency is declared in `requirements.txt`:
	- `drf-standardized-errors==0.15.0`

2. Django settings require it in `newsletter_maker/settings/base.py`:
	- `"drf_standardized_errors"` is present in `INSTALLED_APPS`

3. The freshly built local image is good.
	This command succeeds:

```bash
docker run --rm newsletter-maker-app:dev python -c "import sys; print(sys.executable); import drf_standardized_errors; print(drf_standardized_errors.__file__)"
```

Observed result:

```text
/usr/local/bin/python
/usr/local/lib/python3.13/site-packages/drf_standardized_errors/__init__.py
```

4. The running Django service container claims to use the same image ID as the good image.

Observed:

```bash
docker inspect newsletter-maker-django-1 --format '{{.Id}} {{.Image}} {{.Config.Image}}'
```

Result was:

```text
<container-id> sha256:6e0170b468e9316f0dfdcb9e2a52d4d45c22e9f888ea752f35373f70c0579cf8 docker.io/library/newsletter-maker-app:dev
```

5. The running Django container still cannot see the package files or pip metadata.

Observed inside live container:

```bash
docker compose exec django sh -lc "ls -d /usr/local/lib/python3.13/site-packages/drf_standardized_errors* 2>/dev/null || true; python -m pip show drf-standardized-errors || true"
```

Result:

```text
WARNING: Package(s) not found: drf-standardized-errors
```

6. The live Django container mount set looks normal and only bind-mounts the repo at `/app`.

Observed:

```bash
docker inspect newsletter-maker-django-1 --format '{{json .Mounts}}'
```

Result:

```json
[{"Type":"bind","Source":"/home/kevin/Repos/newsletter-maker","Destination":"/app","Mode":"","RW":true,"Propagation":"rprivate"}]
```

## Best Current Hypothesis

There is a runtime divergence between the fresh image and the live Compose service container, even though the service container reports the same backing image ID.

Most likely remaining explanation:

- the live Django container writable layer has diverged and is hiding/removing files under site-packages, or
- there is some Compose/container lifecycle oddity involving the running service container that is not visible from the static image inspection.

## Next Steps To Resume Tomorrow

1. Inspect container filesystem diff for the live Django service container.

	Commands to run:

```bash
docker diff newsletter-maker-django-1 | grep drf_standardized_errors || true
docker diff newsletter-maker-django-1 | head -200
```

	Note: these were about to be run when work stopped; the tool calls were cancelled by the user.

2. If the diff shows site-packages deletions or unexpected mutations, remove and recreate the Django/celery service containers again and re-test import immediately.

3. If the diff is clean, compare a full directory listing of `/usr/local/lib/python3.13/site-packages` between:
	- `docker run --rm newsletter-maker-app:dev ...`
	- `docker compose exec django ...`

4. Once `docker compose exec django python -c "import drf_standardized_errors; print('ok')"` works, rerun:

```bash
just seed
```

5. After `just seed` works, validate the seeded UI/admin state manually.

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

## Files Changed Today

- `core/management/commands/seed_demo.py`
- `core/tests/test_embeddings.py`
- `justfile`
- `SESSION.md`

