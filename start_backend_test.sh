#!/bin/bash
set -a
source .env
set +a
export GOOGLE_CLOUD_PROJECT=gen-lang-client-0860749390
python -m uvicorn backend.main:app --port 8001 --host 127.0.0.1 > backend_test.log 2>&1 &
echo $! > backend_test.pid
sleep 3
cat backend_test.log
