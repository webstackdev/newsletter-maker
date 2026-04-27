set dotenv-load := true

compose := "docker compose"

backend-install:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 -m pip install -r requirements.txt

frontend-install:
    cd frontend && npm install

install:
    just backend-install
    just frontend-install

backend-dev:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} up django celery-worker celery-beat postgres redis qdrant nginx

frontend-dev:
    if [ ! -f frontend/.env.local ]; then cp frontend/.env.example frontend/.env.local; fi
    cd frontend && npm run dev

dev:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} up

backend-build:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} build django

frontend-build:
    if [ ! -f frontend/.env.local ]; then cp frontend/.env.example frontend/.env.local; fi
    cd frontend && npm run build

build:
    just backend-build
    just frontend-build

frontend-typecheck:
    if [ ! -f frontend/.env.local ]; then cp frontend/.env.example frontend/.env.local; fi
    cd frontend && npm run typecheck

backend-lint:
    if [ ! -f .env ]; then cp .env.example .env; fi
    ruff check manage.py core newsletter_maker tests
    djlint core/templates --check
    python3 -m mypy manage.py core newsletter_maker tests
    pre-commit run --all-files check-yaml
    pre-commit run --all-files end-of-file-fixer
    pre-commit run --all-files trailing-whitespace
    python3 manage.py check

frontend-lint:
    if [ ! -f frontend/.env.local ]; then cp frontend/.env.example frontend/.env.local; fi
    cd frontend && npm run lint

lint:
    just backend-lint
    just frontend-lint

backend-lint-fix:
    if [ ! -f .env ]; then cp .env.example .env; fi
    ruff check manage.py core newsletter_maker tests --fix
    djlint core/templates --reformat
    pre-commit run --all-files end-of-file-fixer
    pre-commit run --all-files trailing-whitespace
    just backend-lint

frontend-lint-fix:
    if [ ! -f frontend/.env.local ]; then cp frontend/.env.example frontend/.env.local; fi
    cd frontend && npm run lint:fix

lint-fix:
    just backend-lint-fix
    just frontend-lint-fix

frontend-format:
    if [ ! -f frontend/.env.local ]; then cp frontend/.env.example frontend/.env.local; fi
    cd frontend && npm run format

frontend-format-check:
    if [ ! -f frontend/.env.local ]; then cp frontend/.env.example frontend/.env.local; fi
    cd frontend && npm run format:check

frontend-test:
    if [ ! -f frontend/.env.local ]; then cp frontend/.env.example frontend/.env.local; fi
    cd frontend && npm run test:run

backend-test:
    python3 -m pytest

test:
    just backend-test
    just frontend-test

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

migrate:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py migrate

seed:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} exec django python manage.py seed_demo

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
