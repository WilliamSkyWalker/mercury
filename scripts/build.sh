#!/bin/bash
set -e

echo "=== Mercury Build Script ==="

# 1. Install Python dependencies
echo "[1/3] Installing Python dependencies..."
pip3 install -r requirements.txt -q

# 2. Install frontend dependencies & build
echo "[2/3] Building frontend..."
cd mercury-frontend
npm install --silent
npm run build
cd ..

# 3. Collect static files
echo "[3/3] Collecting static files..."
python3 manage.py collectstatic --noinput -q

echo ""
echo "=== Build complete ==="
echo "Database schemas are managed manually with scripts/mercury_mysql_schema.sql"
echo "Start server: python3 manage.py runserver 0.0.0.0:8000"
