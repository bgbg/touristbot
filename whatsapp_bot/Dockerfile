# Multi-stage build for smaller image size
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY whatsapp_bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code from project root
# Note: Build context should be project root, not whatsapp_bot/
COPY whatsapp_bot.py /app/
COPY send_whatsapp_message.py /app/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Run the application with gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 300 whatsapp_bot:app
