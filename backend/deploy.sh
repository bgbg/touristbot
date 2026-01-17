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

# Environment variables (loaded from .streamlit/secrets.toml)
GCS_BUCKET="tarasa_tourist_bot_content"
GOOGLE_API_KEY="AIzaSyDUAKaokMm_NstNtgZTAPr7II3XBwpjmQE"

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

# Build and push Docker image
echo "Building Docker image..."
gcloud builds submit --tag ${IMAGE_NAME} --project ${PROJECT_ID}

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
    --set-env-vars "GCS_BUCKET=${GCS_BUCKET},GOOGLE_API_KEY=${GOOGLE_API_KEY},BACKEND_API_KEYS=${BACKEND_API_KEYS}"

echo ""
echo "Deployment complete!"
echo ""
echo "Service URL:"
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --format="value(status.url)")
echo "${SERVICE_URL}"
echo ""
echo "Environment variables configured:"
echo "  - GCS_BUCKET: ${GCS_BUCKET}"
echo "  - GOOGLE_API_KEY: ${GOOGLE_API_KEY:0:20}..."
echo "  - BACKEND_API_KEYS: (keys shown above)"
echo ""
echo "Next steps:"
echo "1. Add to .streamlit/secrets.toml:"
echo "   backend_api_url = \"${SERVICE_URL}\""
echo "   backend_api_key = \"${API_KEY_1:-your-api-key}\""
echo ""
echo "2. Test the deployment:"
echo "   curl ${SERVICE_URL}/health"
echo ""
echo "3. Save API keys securely (you'll need them for frontend and future clients)"
