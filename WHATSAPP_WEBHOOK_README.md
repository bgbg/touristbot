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
BORIS_GORELIK_WABA_ACCESS_TOKEN=your-whatsapp-access-token
BORIS_GORELIK_WABA_PHONE_NUMBER_ID=your-phone-number-id

# Backend API Configuration
BACKEND_API_URL=https://tourism-rag-backend-347968285860.me-west1.run.app
BACKEND_API_KEY=your-backend-api-key

# Optional
META_GRAPH_API_VERSION=v22.0
WHATSAPP_LISTENER_PORT=5001
```

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

- **Persistent Storage**: Conversations stored in `conversations/whatsapp_{phone}.json`
- **Multi-turn Context**: Bot remembers conversation history
- **Reset Command**: Send "reset" or "התחל מחדש" to clear history
- **Default Location**: hefer_valley/agamon_hefer (Agamon Hefer wetlands)

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

## Local Storage

### Conversations
Location: `conversations/whatsapp_{phone}.json`

Structure:
```json
{
  "conversation_id": "whatsapp_972525974655",
  "phone": "972525974655",
  "area": "hefer_valley",
  "site": "agamon_hefer",
  "history": [
    {
      "role": "user",
      "content": "מה יש לראות באגמון חפר?",
      "timestamp": "2026-02-02T14:30:00.000000"
    },
    {
      "role": "assistant",
      "content": "באגמון חפר יש...",
      "timestamp": "2026-02-02T14:30:05.000000"
    }
  ],
  "created_at": "2026-02-02T14:30:00.000000",
  "updated_at": "2026-02-02T14:30:05.000000"
}
```

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

# View conversations
cat conversations/whatsapp_972525974655.json | jq .
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

### Filesystem Permission Errors
```bash
# Create directories
mkdir -p whatsapp_logs conversations

# Check permissions
ls -la whatsapp_logs/ conversations/
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

## Production Migration Path

Phase 1 uses local storage for fast iteration. For production deployment:

### Conversation Storage
Migrate from local JSON files to GCS:
- Use `backend/conversation_storage/conversations.py` (already available)
- Set `GCS_BUCKET` and `GOOGLE_APPLICATION_CREDENTIALS` env vars
- Update `load_conversation()` and `save_conversation()` functions

### Logging
Migrate from local JSONL to Cloud Logging:
- Use Cloud Logging API
- Update `log_event()` function to write to Cloud Logging
- Enable `read_logs.py --source gcp` flag

### Deployment
Deploy to Cloud Run:
- Create `Dockerfile` for bot
- Deploy to Cloud Run in `me-west1` region (same as backend)
- Configure webhook URL to Cloud Run service URL
- Set environment variables in Cloud Run

## Development Workflow

1. **Start bot**: `python whatsapp_bot.py`
2. **Expose with ngrok**: `ngrok http 5001`
3. **Configure webhook** in Meta Console
4. **Send test messages** via WhatsApp
5. **Check logs**: `python read_logs.py --date 2026-02-02`
6. **Verify conversations**: `cat conversations/whatsapp_*.json | jq .`
7. **Make changes** and restart bot

## Architecture Decisions

### Why Local Storage (Phase 1)?
- Faster iteration during development
- No cloud dependencies (simpler setup)
- Easier debugging (cat, jq, grep)
- Clear production migration path

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

After successful Phase 1 testing:
1. Add media message support (images, audio, video)
2. Implement interactive menus (buttons, lists, quick replies)
3. Add location switching commands with NLP parsing
4. Migrate to GCS-backed conversation storage
5. Integrate Cloud Logging
6. Deploy to Cloud Run for production
7. Add monitoring and alerting

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
