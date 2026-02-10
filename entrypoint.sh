#!/bin/sh
set -e

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput || true

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || true

# Run passed command
exec "$@"
