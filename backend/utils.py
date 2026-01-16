"""
Backend utility functions (no Streamlit dependencies).
"""

import os
from pathlib import Path


def get_secret(key: str, default: str = None) -> str:
    """
    Get secret from environment variables.

    Backend version - only uses environment variables (no Streamlit secrets).

    Args:
        key: The secret key to retrieve
        default: Optional default value if key is not found

    Returns:
        The secret value

    Raises:
        KeyError: If key is not found and no default is provided
    """
    # Try environment variable
    value = os.getenv(key)
    if value is not None:
        return value

    # Use default if provided
    if default is not None:
        return default

    # Key not found and no default provided
    raise KeyError(
        f"Secret '{key}' not found. Please set the {key} environment variable."
    )


def load_env_file(env_file: str = ".env"):
    """
    Load environment variables from a .env file.

    Args:
        env_file: Path to .env file (default: .env)
    """
    env_path = Path(env_file)
    if not env_path.exists():
        return

    # Simple .env file parser (key=value format)
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse key=value
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # Set environment variable if not already set
                if key not in os.environ:
                    os.environ[key] = value
