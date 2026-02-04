"""
Backend API client for Tourism RAG system.

Provides interface for calling the QA endpoint with conversation history
and location context.
"""

from __future__ import annotations

import time
from typing import Dict, Any

import requests

from .logging_utils import eprint
from .retry import retry


class BackendClient:
    """
    Backend API client for Tourism RAG QA endpoint.

    Handles communication with the backend FastAPI service running on Cloud Run.
    Uses exponential backoff retry for transient failures.
    """

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize backend API client.

        Args:
            base_url: Backend API base URL (e.g., "https://tourism-rag-backend-...run.app")
            api_key: Backend API authentication key
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @retry(max_attempts=3, base_delay=1.0, max_delay=4.0, logger=eprint)
    def call_qa_endpoint(
        self,
        conversation_id: str,
        area: str,
        site: str,
        query: str
    ) -> Dict[str, Any]:
        """
        Call backend /qa endpoint with retry logic.

        Uses exponential backoff retry (3 attempts: 1s, 2s, 4s delays).
        Retries on 5xx server errors and timeouts.

        Args:
            conversation_id: Unique conversation identifier
            area: Location area (Hebrew name)
            site: Location site (Hebrew name)
            query: User query text

        Returns:
            Backend response dictionary with keys:
                - response_text: LLM response text
                - citations: List of citation objects (optional)
                - images: List of image objects (optional)
                - should_include_images: Boolean flag (optional)
                - image_relevance: List of relevance scores (optional)
                - error: Error message if failed (optional)

        Raises:
            Exception: On final retry failure (after 3 attempts)

        Example:
            client = BackendClient("https://backend.run.app", "api-key")
            response = client.call_qa_endpoint(
                "whatsapp_972501234567",
                "עמק חפר",
                "אגמון חפר",
                "מה יש לראות באגמון?"
            )
            print(response["response_text"])
        """
        url = f"{self.base_url}/qa"
        payload = {
            "conversation_id": conversation_id,
            "area": area,
            "site": site,
            "query": query,
        }

        start_time = time.time()

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=60)
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                result = response.json()
                return result
            else:
                # Retry on 5xx server errors
                if response.status_code >= 500:
                    eprint(f"[BACKEND] Server error {response.status_code}, will retry")
                    raise Exception(f"Backend error: {response.status_code}")
                else:
                    # 4xx errors are not retryable (client error)
                    eprint(f"[BACKEND] Client error {response.status_code}: {response.text[:500]}")
                    return {
                        "error": f"Backend error: {response.status_code}",
                        "response_text": "מצטער, אירעה שגיאה בשרת. אנא נסה שוב מאוחר יותר.",
                    }

        except requests.exceptions.Timeout:
            eprint(f"[BACKEND] Timeout after {time.time() - start_time:.1f}s, will retry")
            raise Exception("Backend timeout")

        except requests.exceptions.RequestException as e:
            eprint(f"[BACKEND] Request exception: {type(e).__name__}: {e}, will retry")
            raise Exception(f"Backend request failed: {e}")
