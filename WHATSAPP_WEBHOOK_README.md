# WhatsApp Bot - Tourism RAG Integration

Complete WhatsApp bot that receives messages via webhook, processes them through the tourism backend API, and sends intelligent responses.

## Architecture

The bot combines three main components:
1. **Webhook Listener**: Receives incoming WhatsApp messages
2. **RAG Integration**: Processes queries through backend File Search API
3. **Message Sender**: Sends responses back via WhatsApp API

All components are unified in `whatsapp_bot.py` for simplicity.

## Prerequisites

1. **Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **ngrok** for local testing:
   ```bash
   brew install ngrok  # macOS
   # or download from https://ngrok.com
   ```

3. **WhatsApp Business API** access configured

4. **Backend API** running at:
   ```
   https://tourism-rag-backend-347968285860.me-west1.run.app
   ```

## Environment Variables

Add to your `.env` file:

```bash
# WhatsApp Webhook Verification
WHATSAPP_VERIFY_TOKEN=my-super-secret-verify-token-12345

# WhatsApp API Credentials
# NOTE: Variable names changed from BORIS_GORELIK_WABA_* to WHATSAPP_*
# If upgrading, update your .env file accordingly
WHATSAPP_ACCESS_TOKEN=your-whatsapp-access-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id

# Backend API Configuration
BACKEND_API_URL=https://tourism-rag-backend-347968285860.me-west1.run.app
BACKEND_API_KEY=your-backend-api-key

# GCS Storage for Conversations (REQUIRED)
GCS_BUCKET=tarasa_tourist_bot_content

# Optional
META_GRAPH_API_VERSION=v22.0
WHATSAPP_LISTENER_PORT=5001
```

### Google Cloud Authentication

For local development, authenticate with Google Cloud:

```bash
# Option 1: Application Default Credentials (Recommended)
gcloud auth application-default login

# Option 2: Service Account (Alternative)
# Set path to service account JSON file
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

For Cloud Run production, authentication is automatic via Cloud Run service account (requires `roles/storage.objectAdmin` IAM role on GCS bucket).

### Getting WhatsApp Credentials

1. Go to [Meta Developer Console](https://developers.facebook.com/)
2. Create or select your WhatsApp Business app
3. Find **Access Token** under WhatsApp → API Setup
4. Find **Phone Number ID** under WhatsApp → API Setup
5. Set verification token (any secure random string)

## Quick Start

### 1. Start the Bot

```bash
# Activate conda environment
conda activate tarasa

# Run the bot
python whatsapp_bot.py
```

The server will start on port 5001 (configurable via `WHATSAPP_LISTENER_PORT`).

### 2. Expose with ngrok

In a separate terminal:

```bash
ngrok http 5001
```

You'll see:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:5001
```

Copy the `https://` URL.

### 3. Configure Webhook in Meta

1. Go to **WhatsApp** → **Configuration** in Meta Developer Console
2. Click **Edit** under Webhook
3. Enter:
   - **Callback URL**: `https://abc123.ngrok-free.app/webhook`
   - **Verify Token**: Your `WHATSAPP_VERIFY_TOKEN` from `.env`
4. Click **Verify and Save**
5. Subscribe to:
   - `messages` (incoming messages)
   - `message_status` (delivery/read receipts)

### 4. Test It!

Send a message to your WhatsApp Business number. The bot will:
1. Receive the message via webhook
2. Process it through the tourism backend
3. Send an intelligent response about the location

## Features

### Conversation Management

- **Persistent Storage**: Conversations stored in Google Cloud Storage at `gs://{bucket}/conversations/whatsapp_{phone}.json`
- **Multi-turn Context**: Bot remembers conversation history across deployments
- **Reset Command**: Send "reset" or "התחל מחדש" to clear history
- **Default Location**: hefer_valley/agamon_hefer (Agamon Hefer wetlands)
- **Fail-fast Behavior**: If GCS is unavailable, the bot returns an error message (no local fallback)

### Error Handling

- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s delays)
- **Timeouts**: 60s for backend API, 30s for WhatsApp API
- **Fallback Messages**: Hebrew error messages for users
- **Graceful Degradation**: Bot continues working even if storage fails

### Logging

- **Daily Log Files**: `whatsapp_logs/{YYYY-MM-DD}.jsonl`
- **Structured Logging**: JSONL format with correlation IDs
- **Log Events**:
  - `incoming_webhook`: Raw webhook payloads
  - `incoming_message`: Parsed incoming messages
  - `backend_request`: RAG API calls
  - `backend_response`: RAG API responses
  - `outgoing_message`: Sent WhatsApp messages
  - `status_update`: Message delivery status
  - `error`: All errors with full context

### Supported Features

✅ **Text messages** (incoming and outgoing)
✅ **Hebrew RTL text** support
✅ **Conversation history** persistence
✅ **Citation integration** from File Search
✅ **Error recovery** with retries
❌ **Media messages** (images, audio, video) - Future phase
❌ **Interactive menus** (buttons, lists) - Future phase
❌ **Location switching** commands - Stub in Phase 1

## API Endpoints

### `GET /webhook`
Webhook verification (used by Meta during setup).

**Parameters:**
- `hub.mode`: "subscribe"
- `hub.verify_token`: Your verification token
- `hub.challenge`: Challenge string

**Response:**
- 200 with challenge if token matches
- 403 if invalid

### `POST /webhook`
Receives incoming messages and status updates.

**Request:** JSON webhook payload from Meta
**Response:** 200 OK with `{"status": "ok"}`

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-02T14:30:00.000000"
}
```

## Storage

### Conversations
Location: `gs://{GCS_BUCKET}/conversations/whatsapp_{phone}.json`

Structure:
```json
{
  "conversation_id": "whatsapp_972525974655",
  "area": "hefer_valley",
  "site": "agamon_hefer",
  "messages": [
    {
      "role": "user",
      "content": "מה יש לראות באגמון חפר?",
      "timestamp": "2026-02-02T14:30:00.000000Z",
      "citations": null,
      "images": null
    },
    {
      "role": "assistant",
      "content": "באגמון חפר יש...",
      "timestamp": "2026-02-02T14:30:05.000000Z",
      "citations": [...],
      "images": [...]
    }
  ],
  "created_at": "2026-02-02T14:30:00.000000Z",
  "updated_at": "2026-02-02T14:30:05.000000Z"
}
```

**Note**: Conversations persist across bot restarts and Cloud Run deployments. All conversations are visible in the admin backoffice UI.

### Logs
Location: `whatsapp_logs/{YYYY-MM-DD}.jsonl`

Example:
```json
{
  "timestamp": "2026-02-02T14:30:00.000000",
  "event_type": "incoming_message",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": {
    "from": "972525974655",
    "type": "text",
    "message_id": "wamid.test123"
  }
}
```

## Log Reader Utility

Enhanced log reader with filtering:

```bash
# View today's logs
python read_logs.py

# View specific date
python read_logs.py --date 2026-02-02

# Filter by phone number
python read_logs.py --phone 972525974655

# Filter by event type
python read_logs.py --event incoming_message

# Show summary statistics
python read_logs.py --summary
```

**Features:**
- Filter by date, phone, event type
- RTL (Hebrew) text support with `python-bidi`
- Summary statistics (messages, errors, latency)
- Correlation ID tracking

**Alternative:** Use `show_messages.py` for simple message viewing (supports incoming + outgoing messages).

## Testing

### Webhook Verification
```bash
curl "http://localhost:5001/webhook?hub.mode=subscribe&hub.verify_token=your-token&hub.challenge=test123"
# Should return: test123
```

### Health Check
```bash
curl http://localhost:5001/health
```

### Send Test Message
From your phone, send a message to the WhatsApp Business number. Example:
```
מה יש לראות באגמון חפר?
```

The bot will respond with tourism information about Agamon Hefer.

### Check Logs
```bash
# Real-time logs
tail -f whatsapp_logs/$(date +%Y-%m-%d).jsonl | jq .

# View with log reader
python read_logs.py --date $(date +%Y-%m-%d)

# View conversations from GCS
gsutil cat gs://tarasa_tourist_bot_content/conversations/whatsapp_972525974655.json | jq .

# List all conversations
gsutil ls gs://tarasa_tourist_bot_content/conversations/
```

## Troubleshooting

### Webhook Verification Fails
- ✅ Check verify token matches in `.env` and Meta Console
- ✅ Ensure ngrok is running
- ✅ Check listener logs: look for `[VERIFICATION]` messages

### No Response from Bot
1. Check backend API is running:
   ```bash
   curl -H "Authorization: Bearer $BACKEND_API_KEY" \
     $BACKEND_API_URL/locations
   ```
2. Check bot logs for errors: `python read_logs.py --event error`
3. Verify environment variables are set: `echo $BACKEND_API_KEY`

### ngrok Disconnects
- Free tier sessions expire after 2 hours
- Restart ngrok and update webhook URL in Meta Console
- Consider ngrok paid plan for reserved domains

### GCS Authentication Errors
```bash
# Check ADC authentication
gcloud auth application-default print-access-token

# Re-authenticate if needed
gcloud auth application-default login

# Verify bucket access
gsutil ls gs://tarasa_tourist_bot_content/conversations/
```

### Hebrew Text Displays Incorrectly
```bash
# Install python-bidi for proper RTL rendering
pip install python-bidi
```

### Backend Timeout
- Default timeout: 60 seconds
- Check backend API health
- Check network connectivity
- Review backend logs in Cloud Run Console

## Cloud Run Deployment

The bot is production-ready for Cloud Run deployment:

### Prerequisites
- Cloud Run service account with IAM role: `roles/storage.objectAdmin` on GCS bucket
- Environment variables configured in Cloud Run

### Deployment Steps

1. **Verify IAM roles**:
   ```bash
   gcloud projects get-iam-policy PROJECT_ID \
     --flatten="bindings[].members" \
     --filter="bindings.role:roles/storage.objectAdmin"
   ```

2. **Build and deploy**:
   ```bash
   # Build container image
   gcloud builds submit --tag gcr.io/PROJECT_ID/whatsapp-bot

   # Deploy to Cloud Run
   gcloud run deploy whatsapp-bot \
     --image gcr.io/PROJECT_ID/whatsapp-bot \
     --region me-west1 \
     --platform managed \
     --no-allow-unauthenticated \
     --set-env-vars GCS_BUCKET=tarasa_tourist_bot_content,BACKEND_API_URL=...,BACKEND_API_KEY=...,WHATSAPP_ACCESS_TOKEN=...,WHATSAPP_PHONE_NUMBER_ID=...,WHATSAPP_VERIFY_TOKEN=...,WHATSAPP_APP_SECRET=...
   ```

3. **Update webhook URL** in Meta Console to Cloud Run service URL

### Logging in Production
- Local logs: `whatsapp_logs/` (temporary, for development)
- Future: Migrate to Cloud Logging for production monitoring

## Development Workflow

1. **Authenticate with GCS**: `gcloud auth application-default login`
2. **Start bot**: `python whatsapp_bot.py`
3. **Expose with ngrok**: `ngrok http 5001`
4. **Configure webhook** in Meta Console
5. **Send test messages** via WhatsApp
6. **Check logs**: `python read_logs.py --date 2026-02-02`
7. **Verify conversations**: `gsutil cat gs://tarasa_tourist_bot_content/conversations/whatsapp_*.json | jq .`
8. **Make changes** and restart bot

## Architecture Decisions

### Why GCS Storage?
- Conversations persist across Cloud Run deployments (ephemeral filesystem)
- All instances share same conversation data (no data divergence)
- Admin backoffice UI can view/manage WhatsApp conversations
- Production-ready architecture from day one
- Uses same storage backend as RAG API

### Why Unified Bot File?
- Simpler to understand and maintain
- All logic in one place
- Easier to test and debug
- No inter-process communication needed

### Why Backend API Integration?
- Reuses all existing RAG infrastructure
- File Search, image handling, citations already implemented
- Consistent with backend architecture
- Production-ready from Phase 1

## Security Notes

1. **Environment Variables**: Never commit `.env` file
2. **API Keys**: Rotate regularly, use secret management in production
3. **Webhook Verification**: Always validate verify token
4. **HTTPS Required**: Meta requires HTTPS (ngrok provides this)
5. **Request Validation**: In production, verify webhook requests are from Meta (signature validation)
6. **Rate Limiting**: WhatsApp API limits: 80 messages/sec, 1000 conversations/day

## Next Steps

1. Add media message support (images, audio, video)
2. Implement interactive menus (buttons, lists, quick replies)
3. Add location switching commands with NLP parsing
4. Integrate Cloud Logging (replace local JSONL logs)
5. Deploy to Cloud Run for production
6. Add monitoring and alerting (Cloud Monitoring integration)
7. Implement rate limiting and quotas

## Support

For issues or questions:
- Check logs: `python read_logs.py`
- Review troubleshooting section above
- Check environment variables: `env | grep -E "(WHATSAPP|BACKEND|WABA)"`
- Test backend API independently
- Verify ngrok is running

## Additional Resources

- [WhatsApp Business Platform Documentation](https://developers.facebook.com/docs/whatsapp)
- [Meta Graph API Reference](https://developers.facebook.com/docs/graph-api)
- [ngrok Documentation](https://ngrok.com/docs)
- Backend API: `backend/README.md`
