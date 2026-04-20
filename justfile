set dotenv-load := true

compose := "docker compose"

dev:
    if [ ! -f .env ]; then cp .env.example .env; fi
    {{compose}} up --build

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
    python3 manage.py test

migrate:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py migrate

seed:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py seed_demo

shell:
    if [ ! -f .env ]; then cp .env.example .env; fi
    python3 manage.py shell