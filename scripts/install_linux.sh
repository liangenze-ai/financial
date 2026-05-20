#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_EXE="$PROJECT_ROOT/.venv/bin/python"

echo "[1/7] Installing base tools..."
sudo apt-get update
sudo apt-get install -y curl gnupg lsb-release ca-certificates apt-transport-https

echo "[2/7] Installing Redis..."
sudo apt-get install -y redis-server
sudo systemctl enable redis-server
sudo systemctl restart redis-server

echo "[3/7] Installing PostgreSQL..."
sudo apt-get install -y postgresql postgresql-contrib libpq-dev
sudo systemctl enable postgresql
sudo systemctl restart postgresql

echo "[4/7] Creating PostgreSQL database and user..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = 'finance_app'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE USER finance_app WITH PASSWORD 'finance_app';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = 'finance_db'" | grep -q 1 \
  || sudo -u postgres createdb -O finance_app finance_db

echo "[5/7] Installing Python dependencies in .venv..."
if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "Python venv not found at $PYTHON_EXE"
  exit 1
fi
"$PYTHON_EXE" -m pip install --upgrade pip
"$PYTHON_EXE" -m pip install -r "$PROJECT_ROOT/backend/requirements.txt"

echo "[6/7] Applying Django migrations..."
cd "$PROJECT_ROOT/backend"
"$PYTHON_EXE" manage.py migrate

echo "[7/7] Completed."
echo "PostgreSQL default: postgresql://finance_app:finance_app@127.0.0.1:5432/finance_db"
echo "Redis default: redis://127.0.0.1:6379"
echo "Start Django: cd backend && $PYTHON_EXE manage.py runserver"
echo "Start Celery: cd backend && $PYTHON_EXE -m celery -A config worker -l info"
