#!/usr/bin/env sh
set -eu

if [ "${BOOTSTRAP_APP:-false}" = "true" ]; then
  python manage.py migrate --noinput

  if [ "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python manage.py shell <<'PY'
import os

from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ["DJANGO_SUPERUSER_USERNAME"]
email = os.environ["DJANGO_SUPERUSER_EMAIL"]
password = os.environ["DJANGO_SUPERUSER_PASSWORD"]

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
PY
  fi
fi

exec "$@"
