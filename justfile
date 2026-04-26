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

frontend-install:
    cd frontend && npm install

frontend-dev:
    cd frontend && npm run dev

frontend-build:
    cd frontend && npm run build

frontend-typecheck:
    cd frontend && npm run typecheck

frontend-lint:
    cd frontend && npm run lint

frontend-lint-fix:
    cd frontend && npm run lint:fix

frontend-format:
    cd frontend && npm run format

frontend-format-check:
    cd frontend && npm run format:check

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
    ruff check manage.py core newsletter_maker tests
    djlint core/templates --check
    python3 -m mypy manage.py core newsletter_maker tests
    pre-commit run --all-files check-yaml
    pre-commit run --all-files end-of-file-fixer
    pre-commit run --all-files trailing-whitespace
    python3 manage.py check

lint-fix:
    if [ ! -f .env ]; then cp .env.example .env; fi
    ruff check manage.py core newsletter_maker tests --fix
    djlint core/templates --reformat
    pre-commit run --all-files end-of-file-fixer
    pre-commit run --all-files trailing-whitespace
    just lint

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
