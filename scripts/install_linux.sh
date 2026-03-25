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

echo "[3/7] Adding MongoDB repository..."
if [[ ! -f /usr/share/keyrings/mongodb-server-8.0.gpg ]]; then
  curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc \
    | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-8.0.gpg
fi

. /etc/os-release
if [[ "${ID}" == "ubuntu" ]]; then
  UBUNTU_CODENAME="${UBUNTU_CODENAME:-jammy}"
  echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu ${UBUNTU_CODENAME}/mongodb-org/8.0 multiverse" \
    | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list >/dev/null
elif [[ "${ID}" == "debian" ]]; then
  DEBIAN_CODENAME="${VERSION_CODENAME:-bookworm}"
  echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/debian ${DEBIAN_CODENAME}/mongodb-org/8.0 main" \
    | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list >/dev/null
else
  echo "Unsupported distro: ${ID}. This script supports Ubuntu/Debian only."
  exit 1
fi

echo "[4/7] Installing MongoDB..."
sudo apt-get update
sudo apt-get install -y mongodb-org
sudo systemctl enable mongod
sudo systemctl restart mongod

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
echo "MongoDB default: mongodb://127.0.0.1:27017"
echo "Redis default: redis://127.0.0.1:6379"
echo "Start Django: cd backend && $PYTHON_EXE manage.py runserver"
echo "Start Celery: cd backend && $PYTHON_EXE -m celery -A config worker -l info"
