#!/usr/bin/env bash
#
# install_linux.sh
#
# Purpose:
#   First-time Linux setup for the finance backend. This script installs Redis,
#   PostgreSQL, PostgreSQL development headers, backend Python dependencies, and
#   applies Django migrations.
#
# When to use:
#   - Fresh Ubuntu/Debian development machine.
#   - CI-like machine where apt-get and sudo are available.
#   - Local environment where Redis and PostgreSQL should be managed by systemd.
#
# When not to use:
#   - Windows machines. Use scripts/install_windows.ps1 instead.
#   - Machines where PostgreSQL/Redis are provided by Docker or external
#     services and you do not want system packages installed.
#   - Production hosts without reviewing package versions, credentials, and
#     service policy first.
#
# What it does:
#   1. Installs base apt tools: curl, gnupg, lsb-release, certificates, HTTPS
#      transport.
#   2. Installs redis-server, enables it, and restarts it.
#   3. Installs postgresql, postgresql-contrib, and libpq-dev, then enables and
#      restarts PostgreSQL.
#   4. Creates PostgreSQL role finance_app with password finance_app if missing.
#   5. Creates PostgreSQL database finance_db owned by finance_app if missing.
#   6. Upgrades pip and installs backend/requirements.txt into .venv.
#   7. Runs Django migrations from backend/.
#
# Required existing files:
#   - .venv/bin/python
#   - backend/requirements.txt
#   - backend/manage.py
#
# Defaults created/used:
#   - PostgreSQL URL: postgresql://finance_app:finance_app@127.0.0.1:5432/finance_db
#   - Redis URL:      redis://127.0.0.1:6379
#
# Usage:
#   ./scripts/install_linux.sh
#
# Common follow-up commands:
#   cd backend && ../.venv/bin/python manage.py runserver
#   cd backend && ../.venv/bin/python -m celery -A config worker -l info
#
# Notes:
#   - The script uses sudo and may prompt for your password.
#   - It is idempotent for the finance_app role and finance_db database.
#   - It performs real system package and service changes.
#
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
