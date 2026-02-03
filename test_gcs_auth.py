#!/usr/bin/env python3
"""Test GCS authentication"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from google.cloud import storage
from google.oauth2 import service_account

# Try loading credentials from secrets.toml
try:
    import streamlit as st
    gcs_creds = st.secrets.get("gcs_credentials")

    if gcs_creds:
        print("✓ Found GCS credentials in secrets.toml")

        # Convert to dict
        if hasattr(gcs_creds, 'to_dict'):
            creds_dict = gcs_creds.to_dict()
        elif not isinstance(gcs_creds, dict):
            creds_dict = dict(gcs_creds)
        else:
            creds_dict = gcs_creds

        print(f"  Service account: {creds_dict.get('client_email')}")
        print(f"  Project ID: {creds_dict.get('project_id')}")

        # Try to create credentials
        try:
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            print("✓ Credentials object created successfully")

            # Try to connect to GCS
            client = storage.Client(
                credentials=credentials,
                project=creds_dict.get("project_id")
            )

            # Test connection by listing buckets
            buckets = list(client.list_buckets(max_results=1))
            print("✓ Successfully authenticated with GCS!")
            print(f"  Found {len(buckets)} bucket(s)")

            # Try accessing the specific bucket
            bucket = client.bucket("tarasa_tourist_bot_content")
            if bucket.exists():
                print("✓ Successfully accessed bucket: tarasa_tourist_bot_content")
            else:
                print("✗ Bucket does not exist: tarasa_tourist_bot_content")

        except Exception as e:
            print(f"✗ Error creating credentials or connecting to GCS: {e}")
            sys.exit(1)
    else:
        print("✗ No GCS credentials found in secrets.toml")
        print("  Will try Application Default Credentials...")

        try:
            # Try with Application Default Credentials
            client = storage.Client(project="gen-lang-client-0860749390")
            buckets = list(client.list_buckets(max_results=1))
            print("✓ Successfully authenticated with Application Default Credentials!")
            print(f"  Found {len(buckets)} bucket(s)")
        except Exception as e:
            print(f"✗ Error with Application Default Credentials: {e}")
            sys.exit(1)

except Exception as e:
    print(f"✗ Error loading secrets: {e}")
    sys.exit(1)
