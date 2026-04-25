set dotenv-load := true

compose := "docker compose"

dev:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} up

build:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} build

build-django:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} build django

up:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} up

up-detached:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} up -d

stop:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} down

restart:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} down
    {{compose}} up --build

restart-no-build:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} down
    {{compose}} up

restart-django:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} build django
    {{compose}} up -d django

createsuperuser:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} exec django python manage.py createsuperuser

changepassword username:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} exec django python manage.py changepassword {{username}}

lint:
    if [ ! -f .env ]; then cp .env.example .env; fi
    hadolint --ignore DL3008 --ignore DL3013 docker/web/Dockerfile
    docker buildx build --check --file docker/web/Dockerfile . >/dev/null
    python3 -m compileall manage.py core newsletter_maker
    python3 manage.py check

test:
    python3 -m pytest

migrate:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py migrate

seed:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py seed_demo

embed-all:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py sync_embeddings

embed-tenant tenant_id:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py sync_embeddings --tenant-id {{tenant_id}}

embed-smoke:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py embedding_smoke

embed-smoke-content content_id:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py embedding_smoke --content-id {{content_id}}

shell:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py shell