#!/bin/bash
set -e

# WhatsApp Bot Deployment Script for Google Cloud Run
# This script deploys the WhatsApp bot as a public-facing service for Meta webhook

echo "========================================"
echo "WhatsApp Bot Deployment to Cloud Run"
echo "========================================"

# Configuration (can be overridden via environment variables)
PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0860749390}"
REGION="${GCP_REGION:-me-west1}"
SERVICE_NAME="whatsapp-bot"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

# Validate required environment variables
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Please create it with required variables:"
    echo "  WHATSAPP_VERIFY_TOKEN"
    echo "  WHATSAPP_ACCESS_TOKEN"
    echo "  WHATSAPP_PHONE_NUMBER_ID"
    echo "  WHATSAPP_SECRET_TOKEN"
    echo "  WHATSAPP_APP_SECRET"
    echo "  BACKEND_API_KEY"
    echo "  GCS_BUCKET"
    exit 1
fi

# Load environment variables
source .env

# Check required variables
REQUIRED_VARS=(
    "WHATSAPP_VERIFY_TOKEN"
    "WHATSAPP_ACCESS_TOKEN"
    "WHATSAPP_PHONE_NUMBER_ID"
    "WHATSAPP_SECRET_TOKEN"
    "WHATSAPP_APP_SECRET"
    "BACKEND_API_KEY"
    "GCS_BUCKET"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "ERROR: Missing required environment variable: $var"
        exit 1
    fi
done

echo ""
echo "Configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service Name: $SERVICE_NAME"
echo "  Image: $IMAGE_NAME"
echo ""

# Build the container image using Cloud Build
echo "Building container image..."
gcloud builds submit \
    --config=cloudbuild.whatsapp.yaml \
    --project "$PROJECT_ID" \
    .

if [ $? -ne 0 ]; then
    echo "ERROR: Image build failed"
    exit 1
fi

echo ""
echo "Deploying to Cloud Run..."

# Deploy to Cloud Run
# IMPORTANT: --allow-unauthenticated for Meta webhook verification
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_NAME" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 3600 \
    --max-instances 10 \
    --project "$PROJECT_ID" \
    --set-env-vars "WHATSAPP_VERIFY_TOKEN=${WHATSAPP_VERIFY_TOKEN},WHATSAPP_ACCESS_TOKEN=${WHATSAPP_ACCESS_TOKEN},WHATSAPP_PHONE_NUMBER_ID=${WHATSAPP_PHONE_NUMBER_ID},WHATSAPP_SECRET_TOKEN=${WHATSAPP_SECRET_TOKEN},WHATSAPP_APP_SECRET=${WHATSAPP_APP_SECRET},BACKEND_API_URL=https://tourism-rag-backend-347968285860.me-west1.run.app,BACKEND_API_KEY=${BACKEND_API_KEY},GCS_BUCKET=${GCS_BUCKET}"

if [ $? -ne 0 ]; then
    echo "ERROR: Deployment failed"
    exit 1
fi

echo ""
echo "========================================"
echo "Deployment successful!"
echo "========================================"

# Get the service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --format 'value(status.url)')

echo ""
echo "WhatsApp Bot URL: $SERVICE_URL"
echo ""
echo "Configure Meta Webhook URL:"
echo "  URL: ${SERVICE_URL}/webhook"
echo "  Verify Token: ${WHATSAPP_VERIFY_TOKEN}"
echo ""
echo "Subscribe to webhook fields:"
echo "  - messages"
echo ""
