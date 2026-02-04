"""
Retry utility with exponential backoff.

Provides generic retry decorator for handling transient failures in external API calls.
"""

from __future__ import annotations

import functools
import time
from typing import Callable, TypeVar, Any, Tuple, Type

# Type variables for generic decorator
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 4.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger: Callable[[str], None] | None = None
) -> Callable[[F], F]:
    """
    Decorator for exponential backoff retry logic.

    Retries a function up to max_attempts times with exponential backoff delay.
    Delay calculation: min(base_delay * (2 ** attempt), max_delay) seconds.

    Args:
        max_attempts: Number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        max_delay: Maximum delay in seconds (default: 4.0)
        exceptions: Tuple of exceptions to catch and retry (default: Exception)
        logger: Optional logging function for retry events (default: None)

    Returns:
        Decorated function with retry logic

    Example:
        @retry(max_attempts=3, base_delay=1.0, max_delay=4.0)
        def send_request():
            response = requests.post(url, data=payload)
            return response

        # Retries on failure: 0s → 1s delay → 2s delay → 4s delay → raise
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    # Attempt the function call
                    result = func(*args, **kwargs)
                    return result

                except exceptions as e:
                    last_exception = e

                    # Don't retry on final attempt
                    if attempt >= max_attempts - 1:
                        break

                    # Calculate exponential backoff delay
                    delay = min(base_delay * (2 ** attempt), max_delay)

                    # Log retry attempt if logger provided
                    if logger:
                        logger(
                            f"[RETRY] Attempt {attempt + 1}/{max_attempts} failed "
                            f"with {type(e).__name__}: {e}. Retrying in {delay}s..."
                        )

                    # Wait before retry
                    time.sleep(delay)

            # All retries exhausted, raise last exception
            if last_exception:
                if logger:
                    logger(
                        f"[RETRY] All {max_attempts} attempts failed. "
                        f"Final error: {type(last_exception).__name__}: {last_exception}"
                    )
                raise last_exception

            # Should never reach here, but make type checker happy
            raise RuntimeError("Retry logic error: no exception but no result")

        return wrapper  # type: ignore

    return decorator


def create_retry_decorator(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 4.0,
    logger: Callable[[str], None] | None = None
) -> Callable[[F], F]:
    """
    Factory function to create retry decorator with fixed configuration.

    Useful when you want to create a consistent retry strategy across multiple functions.

    Args:
        max_attempts: Number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        logger: Optional logging function

    Returns:
        Configured retry decorator

    Example:
        eprint = lambda msg: print(msg, file=sys.stderr)
        api_retry = create_retry_decorator(max_attempts=3, base_delay=1.0, logger=eprint)

        @api_retry
        def send_whatsapp_message(...):
            ...

        @api_retry
        def call_backend_api(...):
            ...
    """
    return retry(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exceptions=(Exception,),
        logger=logger
    )
