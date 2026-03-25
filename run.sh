#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Initialize DB if it doesn't exist
if [ ! -f data/wwww.db ]; then
    echo "Initializing database..."
    FLASK_APP=app.py .venv/bin/flask init-db
    FLASK_APP=app.py .venv/bin/flask seed
fi

echo "Starting gunicorn on port 5111..."
exec .venv/bin/gunicorn \
    --bind 0.0.0.0:5111 \
    --workers 4 \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    "app:create_app()"
