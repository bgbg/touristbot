#!/bin/bash
# Local testing script for backend
# Runs uvicorn directly without Docker

set -e

cd "$(dirname "$0")/.."

echo "Starting backend locally..."
echo "Make sure you have activated the tarasa conda environment"
echo ""

# Set test environment variables
export BACKEND_API_KEYS="test-key-123"
export GCS_BUCKET="your-gcs-bucket-name"
export GOOGLE_API_KEY="your-google-api-key"
export PORT=8080

# Run with uvicorn
python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --reload
