#!/bin/bash
# Deployment script for Cloud Run - WhatsApp Bot
# Usage: ./deploy.sh [project-id] [region]
#
# Defaults:
#   - Project: gen-lang-client-0860749390
#   - Region: me-west1 (Tel Aviv, Israel - closest to customers)

set -e
set -o pipefail

# Resolve script directory (works from any working directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID=${1:-"gen-lang-client-0860749390"}
REGION=${2:-"me-west1"}
SERVICE_NAME="whatsapp-bot"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Create secure temporary file for environment variables
ENV_YAML_FILE=$(mktemp /tmp/whatsapp-bot-env.XXXXXX.yaml)
chmod 600 "${ENV_YAML_FILE}"

# Cleanup trap: ensure temporary file is removed on exit/error
cleanup() {
    rm -f "${ENV_YAML_FILE}"
}
trap cleanup EXIT INT TERM

# Load environment variables from .env file if it exists
if [ -f "${PROJECT_ROOT}/.env" ]; then
    echo "Loading environment variables from project root .env file..."
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
    set +a
elif [ -f "${SCRIPT_DIR}/.env" ]; then
    echo "Loading environment variables from whatsapp_bot/.env file..."
    set -a
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/.env"
    set +a
fi

# Check for required environment variables (including WHATSAPP_APP_SECRET for production security)
required_vars=("WHATSAPP_VERIFY_TOKEN" "WHATSAPP_ACCESS_TOKEN" "WHATSAPP_PHONE_NUMBER_ID" "BACKEND_API_KEY" "WHATSAPP_APP_SECRET")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "Error: Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Please set these in your .env file (project root or whatsapp_bot/.env)"
    exit 1
fi

# Set defaults for optional variables
BACKEND_API_URL=${BACKEND_API_URL:-"https://tourism-rag-backend-347968285860.me-west1.run.app"}
META_GRAPH_API_VERSION=${META_GRAPH_API_VERSION:-"v22.0"}

echo "Deploying WhatsApp Bot to Cloud Run"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Build and push Docker image (from project root, not whatsapp_bot/)
echo "Building Docker image..."
gcloud builds submit --config=whatsapp_bot/cloudbuild.yaml --project ${PROJECT_ID} "${PROJECT_ROOT}"

# Create temporary env vars file for Cloud Run (using secure temp file)
echo "Creating environment variables file..."
cat > "${ENV_YAML_FILE}" <<EOF
WHATSAPP_VERIFY_TOKEN: "${WHATSAPP_VERIFY_TOKEN}"
WHATSAPP_ACCESS_TOKEN: "${WHATSAPP_ACCESS_TOKEN}"
WHATSAPP_PHONE_NUMBER_ID: "${WHATSAPP_PHONE_NUMBER_ID}"
BACKEND_API_URL: "${BACKEND_API_URL}"
BACKEND_API_KEY: "${BACKEND_API_KEY}"
META_GRAPH_API_VERSION: "${META_GRAPH_API_VERSION}"
WHATSAPP_APP_SECRET: "${WHATSAPP_APP_SECRET}"
EOF

# Deploy to Cloud Run with environment variables
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    --project ${PROJECT_ID} \
    --env-vars-file "${ENV_YAML_FILE}"

# Cleanup handled by trap

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
echo "Webhook URL (for Meta Developer Console):"
echo "  ${SERVICE_URL}/webhook"
echo ""
echo "Health Check URL:"
echo "  ${SERVICE_URL}/health"
echo ""
echo "Project Configuration:"
echo "  PROJECT_ID: ${PROJECT_ID}"
echo "  REGION: ${REGION}"
echo "  SERVICE_NAME: ${SERVICE_NAME}"
echo "  BACKEND_API_URL: ${BACKEND_API_URL}"
echo ""
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Test webhook verification (avoid pasting real tokens in shared terminals/logs):"
echo "   curl \"${SERVICE_URL}/webhook?hub.mode=subscribe&hub.challenge=test&hub.verify_token=<YOUR_VERIFY_TOKEN>\""
echo ""
echo "2. Test health check:"
echo "   curl ${SERVICE_URL}/health"
echo ""
echo "3. Update Meta Developer Console webhook:"
echo "   - Navigate to: https://developers.facebook.com/apps"
echo "   - Go to WhatsApp > Configuration > Webhook"
echo "   - Update Callback URL to: ${SERVICE_URL}/webhook"
echo "   - Use your WHATSAPP_VERIFY_TOKEN from .env file"
echo "   - Click 'Verify and Save'"
echo ""
echo "4. Monitor logs:"
echo "   gcloud run logs tail ${SERVICE_NAME} --region ${REGION}"
echo ""
