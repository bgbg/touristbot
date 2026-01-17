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

echo "Deploying Tourism RAG Backend to Cloud Run"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Build and push Docker image
echo "Building Docker image..."
gcloud builds submit --tag ${IMAGE_NAME} --project ${PROJECT_ID}

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --max-instances 10 \
    --project ${PROJECT_ID}

echo ""
echo "Deployment complete!"
echo ""
echo "Service URL:"
gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --format="value(status.url)"
echo ""
echo "Next steps:"
echo "1. Copy the service URL above"
echo "2. Add to .streamlit/secrets.toml:"
echo "   backend_api_url = \"<SERVICE_URL>\""
echo "   backend_api_key = \"your-api-key-from-BACKEND_API_KEYS\""
echo "3. Set environment variables in Cloud Run:"
echo "   - BACKEND_API_KEYS (comma-separated API keys)"
echo "   - GCS_BUCKET (tarasa_tourist_bot_content)"
echo "   - GOOGLE_API_KEY (your Gemini API key)"
