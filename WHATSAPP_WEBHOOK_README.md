# WhatsApp Webhook Listener Setup Guide

This guide walks you through setting up the WhatsApp webhook listener to receive incoming messages.

## Prerequisites

1. Flask installed: `pip install flask`
2. ngrok installed: `brew install ngrok` (macOS) or download from [ngrok.com](https://ngrok.com)
3. WhatsApp Business API access configured

## Setup Steps

### 1. Set Verification Token

Add to your `.env` file:

```bash
WHATSAPP_VERIFY_TOKEN=my-super-secret-verify-token-12345
```

Choose a secure random string. You'll use this when configuring the webhook in Meta.

### 2. Start the Webhook Listener

```bash
python whatsapp_listener.py
```

The server will start on port 5001 (configurable via `WHATSAPP_LISTENER_PORT` env var).

### 3. Expose with ngrok

In a separate terminal:

```bash
ngrok http 5001
```

You'll see output like:

```
Forwarding  https://abc123.ngrok.io -> http://localhost:5001
```

Copy the `https://` URL (e.g., `https://abc123.ngrok.io`).

### 4. Configure Webhook in Meta Developer Console

1. Go to [Meta Developer Console](https://developers.facebook.com/)
2. Select your WhatsApp app
3. Navigate to **WhatsApp** → **Configuration**
4. Under **Webhook**, click **Edit**
5. Enter:
   - **Callback URL**: `https://abc123.ngrok.io/webhook`
   - **Verify Token**: The same token from your `.env` (e.g., `my-super-secret-verify-token-12345`)
6. Click **Verify and Save**
7. Subscribe to webhook fields:
   - `messages` (for incoming messages)
   - `message_status` (for delivery/read receipts)

## API Endpoints

### GET /webhook
Webhook verification endpoint (used by Meta during setup).

**Query Parameters:**
- `hub.mode`: Must be "subscribe"
- `hub.verify_token`: Your verification token
- `hub.challenge`: Challenge string to echo back

**Response:**
- 200 with challenge string if token matches
- 403 if token is invalid

### POST /webhook
Receives incoming messages and status updates.

**Request Body:** JSON webhook payload from Meta

**Response:** 200 OK with `{"status": "ok"}`

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-02T09:44:31.435225"
}
```

### GET /logs
View recent webhook logs (last 50 entries).

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2026-02-02T09:44:42.791925",
      "event_type": "incoming_message",
      "data": {
        "message_id": "wamid.test123",
        "from": "972525974655",
        "timestamp": "1234567890",
        "type": "text",
        "text": "Hello from test!"
      }
    }
  ]
}
```

## Log Files

All webhook events are logged to `whatsapp_logs/{date}.jsonl` in JSONL format (one JSON object per line).

Example log entry:
```json
{
  "timestamp": "2026-02-02T09:44:42.791925",
  "event_type": "incoming_message",
  "data": {
    "message_id": "wamid.test123",
    "from": "972525974655",
    "timestamp": "1234567890",
    "type": "text",
    "text": "Hello from test!"
  }
}
```

## Supported Message Types

The listener extracts information from:

- **text**: Text messages
- **image**: Images with optional caption
- **audio**: Audio messages
- **video**: Videos with optional caption
- **document**: Documents with filename
- **location**: Location shares with coordinates

## Testing Locally

Test verification:
```bash
curl "http://localhost:5001/webhook?hub.mode=subscribe&hub.verify_token=my-super-secret-verify-token-12345&hub.challenge=test123"
```

Test incoming message:
```bash
curl -X POST http://localhost:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "972525974655",
            "id": "test123",
            "timestamp": "1234567890",
            "type": "text",
            "text": {"body": "Test message"}
          }]
        }
      }]
    }]
  }'
```

## Troubleshooting

### Port 5000 already in use
macOS AirPlay uses port 5000. The listener defaults to port 5001, but you can change it:

```bash
export WHATSAPP_LISTENER_PORT=5002
python whatsapp_listener.py
```

### Webhook verification fails
- Check that verify token in `.env` matches the one in Meta Console
- Ensure ngrok is running and URL is correct
- Check listener logs for verification attempts

### Not receiving messages
1. Verify webhook is subscribed to `messages` field in Meta Console
2. Check ngrok is still running (free tier sessions expire after 2 hours)
3. Check listener logs: `tail -f whatsapp_logs/$(date +%Y-%m-%d).jsonl`

## Security Notes

1. **Production Deployment**: This is a development server. For production, use a proper WSGI server (gunicorn, uWSGI)
2. **HTTPS Required**: Meta requires HTTPS for webhooks (ngrok provides this)
3. **Verify Token**: Use a strong, random verification token
4. **Request Validation**: In production, verify webhook requests are from Meta (signature validation)

## Next Steps

After receiving webhooks, you can:
1. Parse incoming messages
2. Process them (e.g., send to your chatbot)
3. Respond using the `try_whatsapp.py` script:
   ```bash
   python try_whatsapp.py <sender_phone> --text "Your response"
   ```

## Example: Simple Echo Bot

```python
# In webhook_handler() function, add after logging:
if msg_type == "text":
    sender = msg_info.get("from")
    text = msg_info.get("text")

    # Echo the message back
    import subprocess
    subprocess.run([
        "python", "try_whatsapp.py",
        sender,
        "--text", f"You said: {text}"
    ])
```
