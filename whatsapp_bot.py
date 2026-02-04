#!/usr/bin/env python3
"""
WhatsApp Bot - Entry point for Tourism RAG integration.

This is the main entry point that preserves backward compatibility.
All application logic has been refactored into the whatsapp/ package.

Usage:
  python whatsapp_bot.py
"""

from __future__ import annotations

import os
import signal
import sys
import subprocess
import time

import requests
from dotenv import load_dotenv

# Import refactored modules
from whatsapp.app import create_app
from whatsapp.dependencies import (
    get_config, get_task_manager, get_message_deduplicator,
    get_conversation_store, get_event_logger, get_conversation_loader,
    get_backend_client, get_whatsapp_client
)
from whatsapp.logging_utils import eprint

# Import for backward compatibility with tests
from backend.gcs_storage import GCSStorage

load_dotenv()

# Backward compatibility: expose app and internal state for tests
# Tests expect to import these directly from whatsapp_bot module
app = create_app()  # Create app instance at module level

# Compatibility exports for tests - expose singletons
_deduplicator = get_message_deduplicator()
_task_manager = get_task_manager()
_conversation_loader = get_conversation_loader()
_backend_client = get_backend_client()
_whatsapp_client = get_whatsapp_client()
_event_logger = get_event_logger()

# Helper accessors for internal state used by tests (backward compatibility)
# These provide a stable interface without exposing implementation details
def get_message_dedup_cache_size() -> int:
    """
    Return the current size of the message deduplication cache.

    This provides a stable interface for tests without exposing the
    underlying cache implementation or private attributes directly.
    """
    return _deduplicator.get_cache_size()


def clear_message_dedup_cache() -> None:
    """
    Clear all entries from the message deduplication cache.

    Thread-safe operation. Useful for testing to reset state between test cases.
    """
    _deduplicator.clear()


def get_active_thread_count() -> int:
    """
    Return the current number of active background threads managed
    by the BackgroundTaskManager.

    This avoids exposing the internal _active_threads collection
    directly while still allowing tests to assert on thread usage.
    """
    return _task_manager.get_active_count()


def clear_active_threads() -> None:
    """
    Clear all active threads from tracking.

    Thread-safe operation. Useful for testing to reset state between test cases.
    Note: This only clears tracking, does not stop running threads.
    """
    _task_manager.clear_active_threads()

# Expose conversation_store for tests
conversation_store = get_conversation_store()

# Compatibility function for tests
def is_duplicate_message(msg_id: str) -> bool:
    """Backward compatibility wrapper for deduplication."""
    return _deduplicator.is_duplicate(msg_id)


# Import other functions that tests might need
from whatsapp.message_handler import process_message
from whatsapp.whatsapp_client import WhatsAppClient

# Compatibility wrappers for tests
def process_message_async(phone: str, text: str, message_id: str, correlation_id: str) -> None:
    """Backward compatibility wrapper for process_message."""
    process_message(
        phone=phone,
        text=text,
        message_id=message_id,
        correlation_id=correlation_id,
        conversation_loader=_conversation_loader,
        backend_client=_backend_client,
        whatsapp_client=_whatsapp_client,
        logger=_event_logger
    )


def load_conversation(phone: str):
    """
    Backward compatibility wrapper for load_conversation.

    Uses module-level conversation_store for test compatibility.
    """
    # For test compatibility, use the module-level conversation_store
    # which can be patched by tests
    conversation_id = f"whatsapp_{phone}"

    try:
        # Try to load existing conversation from GCS
        conv = conversation_store.get_conversation(conversation_id)
        if conv:
            # Check if all messages were expired
            if len(conv.messages) == 0:
                eprint(f"[CONV] Loaded conversation with all messages expired: {conversation_id}")
                eprint(f"[CONV] Starting fresh conversation after expiration")
            else:
                eprint(f"[CONV] Loaded existing conversation: {conversation_id} ({len(conv.messages)} messages)")
            return conv
        else:
            # Create new conversation
            eprint(f"[CONV] Creating new conversation: {conversation_id}")
            config = get_config()
            conv = conversation_store.create_conversation(
                area=config.default_area,
                site=config.default_site,
                conversation_id=conversation_id
            )
            # Save immediately to GCS
            conversation_store.save_conversation(conv)
            return conv
    except Exception as e:
        eprint(f"[ERROR] Failed to load/create conversation: {e}")
        # Fail-fast: re-raise exception to trigger error response
        raise


def call_backend_qa(conversation_id: str, area: str, site: str, query: str, correlation_id: str = None):
    """Backward compatibility wrapper for call_backend_qa."""
    return _backend_client.call_qa_endpoint(conversation_id, area, site, query)


def send_text_message(to_phone: str, text: str, correlation_id: str = None):
    """Backward compatibility wrapper for send_text_message."""
    return _whatsapp_client.send_text_message(to_phone, text)


def normalize_phone(raw: str) -> str:
    """Backward compatibility wrapper for normalize_phone."""
    return WhatsAppClient.normalize_phone(raw)


def download_image_from_url(url: str) -> bytes:
    """Backward compatibility wrapper for download_image_from_url."""
    return WhatsAppClient.download_image_from_url(url)


def send_image_with_retry(to_phone: str, image_url: str, caption: str, correlation_id: str = None):
    """Backward compatibility wrapper for send_image."""
    return _whatsapp_client.send_image(to_phone, image_url, caption)


# Backend process (will be started if USE_LOCAL_BACKEND=true)
backend_process = None


def graceful_shutdown(signum=None, frame=None):
    """
    Graceful shutdown handler - waits for active background threads to complete.

    Called on SIGTERM/SIGINT signals. Waits up to 30 seconds for active threads
    to complete, then exits.

    Args:
        signum: Signal number (from signal handler)
        frame: Current stack frame (from signal handler)
    """
    eprint("\n🛑 Shutdown signal received, waiting for active threads...")

    task_manager = get_task_manager()
    remaining = task_manager.wait_for_completion(max_wait_seconds=30)

    sys.exit(0)


if __name__ == "__main__":
    # Load configuration
    config = get_config()

    # Validate configuration (already done in get_config, but explicit check here)
    config.validate()

    # Register graceful shutdown handlers
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

    eprint("=" * 60)
    eprint("WhatsApp Bot - Tourism RAG Integration")
    eprint("=" * 60)
    eprint(f"Port: {config.port}")
    eprint(f"Verify Token: {config.verify_token}")
    eprint(f"Backend API: {config.backend_api_url}")
    eprint(f"Log Directory: {config.log_dir.absolute()}")
    eprint(f"GCS Bucket: {config.gcs_bucket} (using ADC for authentication)")
    eprint(f"Default Location: {config.default_area}/{config.default_site}")
    eprint(f"Background Task Timeout: {config.background_task_timeout_seconds}s")
    eprint("=" * 60)

    # Only run startup logic once (not in Flask reloader child process)
    # This prevents backend and ngrok from restarting on every code change
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        # Start local backend if USE_LOCAL_BACKEND=true
        if config.use_local_backend:
            try:
                # Kill any existing process on backend port
                eprint(f"\n🔍 Checking for processes on port {config.backend_port}...")
                try:
                    result = subprocess.run(
                        ["lsof", "-ti", f":{config.backend_port}"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.stdout.strip():
                        pids = result.stdout.strip().split('\n')
                        for pid in pids:
                            eprint(f"   Terminating process {pid} on port {config.backend_port}")
                            # Try graceful termination first (SIGTERM)
                            subprocess.run(["kill", pid], timeout=5)
                        # Wait for graceful shutdown
                        time.sleep(2)
                        # Check if any processes still running, force kill if necessary
                        result2 = subprocess.run(
                            ["lsof", "-ti", f":{config.backend_port}"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result2.stdout.strip():
                            remaining_pids = result2.stdout.strip().split('\n')
                            for pid in remaining_pids:
                                eprint(f"   Force killing process {pid} (SIGKILL)")
                                subprocess.run(["kill", "-9", pid], timeout=5)
                            time.sleep(1)
                except Exception as e:
                    eprint(f"   (Could not check/kill processes: {e})")

                eprint(f"🚀 Starting local backend on port {config.backend_port}...")
                # Pass environment variables to backend subprocess
                backend_env = os.environ.copy()
                backend_process = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "backend.main:app",
                     "--reload", "--port", str(config.backend_port), "--host", "127.0.0.1"],
                    env=backend_env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                eprint(f"✓ Backend process started (PID: {backend_process.pid})")
                eprint(f"📡 Backend API: http://localhost:{config.backend_port}")

                # Wait a moment for backend to start
                time.sleep(2)
            except Exception as e:
                eprint(f"⚠️  Warning: Could not start local backend: {e}")
                eprint(f"💡 You can manually run: uvicorn backend.main:app --reload --port {config.backend_port}")
                sys.exit(1)

        # Setup and start ngrok tunnel
        public_url = None
        try:
            # First, check if ngrok is already running
            # ngrok exposes a local API at http://127.0.0.1:4040/api/tunnels
            try:
                ngrok_api_response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
                if ngrok_api_response.status_code == 200:
                    tunnels_data = ngrok_api_response.json()
                    for tunnel in tunnels_data.get("tunnels", []):
                        # Look for tunnel on our port
                        config_addr = tunnel.get("config", {}).get("addr", "")
                        if f"localhost:{config.port}" in config_addr or f"127.0.0.1:{config.port}" in config_addr:
                            public_url = tunnel.get("public_url")
                            if public_url:
                                eprint(f"\n✓ Found existing ngrok tunnel")
                                break
            except Exception:
                # ngrok API not available (not running)
                pass

            # If no existing tunnel found, start ngrok as background process
            if not public_url:
                import shutil
                system_ngrok = shutil.which("ngrok")
                if not system_ngrok:
                    raise Exception("ngrok not found in PATH")

                eprint(f"\n⚡ Starting ngrok tunnel on port {config.port} (background process)...")
                # Start ngrok as detached background process
                subprocess.Popen(
                    [system_ngrok, "http", str(config.port), "--log=stdout"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True  # Detach from parent process
                )

                # Wait for ngrok to start and get the tunnel URL
                for attempt in range(10):
                    time.sleep(1)
                    try:
                        ngrok_api_response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
                        if ngrok_api_response.status_code == 200:
                            tunnels_data = ngrok_api_response.json()
                            for tunnel in tunnels_data.get("tunnels", []):
                                config_addr = tunnel.get("config", {}).get("addr", "")
                                if f"localhost:{config.port}" in config_addr or f"127.0.0.1:{config.port}" in config_addr:
                                    public_url = tunnel.get("public_url")
                                    if public_url:
                                        eprint(f"✓ ngrok tunnel started (persists across bot restarts)")
                                        break
                            if public_url:
                                break
                    except Exception:
                        # Retry on any error (network, JSON parsing, etc.)
                        continue

                if not public_url:
                    raise Exception("Failed to get ngrok tunnel URL after 10 seconds")

            if public_url:
                eprint(f"\n🌐 Local:      http://127.0.0.1:{config.port}")
                eprint(f"🌐 Public:     {public_url}")
                eprint(f"\n📋 Webhook URL for Meta Console:")
                eprint(f"   {public_url}/webhook")
                eprint("=" * 60)

        except Exception as e:
            eprint(f"\n⚠️  Warning: Could not start ngrok: {e}")
            eprint(f"💡 You can manually run: ngrok http {config.port}")
            eprint(f"🌐 Local only: http://127.0.0.1:{config.port}")
            eprint("=" * 60)

    # Create Flask app
    app = create_app()

    # Run Flask app with auto-reload enabled
    # Default: debug mode OFF for security (must be explicitly enabled via FLASK_DEBUG)
    flask_debug_env = os.getenv("FLASK_DEBUG")
    if flask_debug_env is None:
        debug_mode = False
        use_reloader = False
    else:
        debug_mode = flask_debug_env.lower() in ("1", "true", "yes", "on")
        use_reloader = debug_mode

    try:
        app.run(host="0.0.0.0", port=config.port, debug=debug_mode, use_reloader=use_reloader)
    finally:
        # Clean up backend process on exit
        if backend_process and backend_process.poll() is None:
            eprint("\n🛑 Stopping local backend...")
            backend_process.terminate()
            backend_process.wait(timeout=5)
            eprint("✓ Backend stopped")
