#!/bin/bash
# Deployment script for Cloud Run - Tourism RAG Backend
# Usage: ./deploy.sh [project-id] [region]
#
# Defaults:
#   - Project: gen-lang-client-0860749390
#   - Region: me-west1 (Tel Aviv, Israel - closest to customers)

set -e

PROJECT_ID=${1:-"gen-lang-client-0860749390"}
REGION=${2:-"me-west1"}
SERVICE_NAME="tourism-rag-backend"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Load environment variables from .env file if it exists
if [ -f ../.env ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' ../.env | xargs)
elif [ -f .env ]; then
    echo "Loading environment variables from backend/.env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Environment variables
GCS_BUCKET="tarasa_tourist_bot_content"

# Check for required environment variables
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "Error: GOOGLE_API_KEY environment variable is required"
    echo "Either:"
    echo "  1. Create a .env file in project root with: GOOGLE_API_KEY=your-key"
    echo "  2. Or export it: export GOOGLE_API_KEY=your-key"
    exit 1
fi

# Generate secure API keys if not provided
# You can override these by setting BACKEND_API_KEYS environment variable before running
if [ -z "$BACKEND_API_KEYS" ]; then
    # Generate 2 random API keys for production use
    API_KEY_1=$(openssl rand -hex 32)
    API_KEY_2=$(openssl rand -hex 32)
    BACKEND_API_KEYS="${API_KEY_1},${API_KEY_2}"
    echo "Generated new API keys:"
    echo "  Key 1: ${API_KEY_1}"
    echo "  Key 2: ${API_KEY_2}"
    echo ""
    echo "IMPORTANT: Save these keys securely! You'll need them to configure the frontend."
    echo ""
fi

echo "Deploying Tourism RAG Backend to Cloud Run"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Build and push Docker image (from project root, not backend/)
echo "Building Docker image..."
cd ..
gcloud builds submit --config=backend/cloudbuild.yaml --project ${PROJECT_ID} .
cd backend

# Create temporary env vars file for Cloud Run
echo "Creating environment variables file..."
cat > .env.yaml <<EOF
GCS_BUCKET: "${GCS_BUCKET}"
GOOGLE_API_KEY: "${GOOGLE_API_KEY}"
BACKEND_API_KEYS: "${BACKEND_API_KEYS}"
EOF

# Deploy to Cloud Run with environment variables
echo "Deploying to Cloud Run with environment variables..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --max-instances 10 \
    --project ${PROJECT_ID} \
    --env-vars-file .env.yaml

# Clean up
rm -f .env.yaml

echo ""
echo "Deployment complete!"
echo ""
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --format="value(status.url)")

echo "=========================================="
echo "DEPLOYMENT SUMMARY"
echo "=========================================="
echo ""
echo "Service URL:"
echo "  ${SERVICE_URL}"
echo ""
echo "Project Configuration:"
echo "  PROJECT_ID: ${PROJECT_ID}"
echo "  REGION: ${REGION}"
echo "  SERVICE_NAME: ${SERVICE_NAME}"
echo "  GCS_BUCKET: ${GCS_BUCKET}"
echo ""
echo "Environment Variables (Cloud Run):"
echo "  GCS_BUCKET: ${GCS_BUCKET}"
echo "  GOOGLE_API_KEY: ${GOOGLE_API_KEY}"
echo "  BACKEND_API_KEYS: ${BACKEND_API_KEYS}"
echo ""
echo "Backend API Keys (for authentication):"
# Split the keys if they exist
if [ -n "$BACKEND_API_KEYS" ]; then
    IFS=',' read -ra KEYS <<< "$BACKEND_API_KEYS"
    for i in "${!KEYS[@]}"; do
        echo "  Key $((i+1)): ${KEYS[$i]}"
    done
fi
echo ""
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Add to .streamlit/secrets.toml:"
echo "   backend_api_url = \"${SERVICE_URL}\""
if [ -n "$BACKEND_API_KEYS" ]; then
    IFS=',' read -ra KEYS <<< "$BACKEND_API_KEYS"
    echo "   backend_api_key = \"${KEYS[0]}\""
fi
echo ""
echo "2. Test the deployment:"
echo "   curl ${SERVICE_URL}/health"
echo ""
echo "3. Save API keys securely (you'll need them for frontend and future clients)"
