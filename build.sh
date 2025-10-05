#!/bin/bash
# Build script for Railway deployment

set -e  # Exit on error

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate --noinput

echo "Build completed successfully!"
