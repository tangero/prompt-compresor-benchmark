#!/usr/bin/env bash
# Stáhne při buildu modely, které Headroom jinak tahá za běhu (Kompress z HF,
# ONNX runtime). Spustí proxy proti neexistujícímu upstreamu a pošle jí velký
# kompresovatelný požadavek; odpověď je nepodstatná, jde o naplnění cache.
set -u
headroom --version || true
if headroom install --help >/dev/null 2>&1; then headroom install models </dev/null || true; fi
# Model Kompress explicitně: líné stažení při první kompresi doběhne až po ukončení proxy.
python3 -c "from huggingface_hub import snapshot_download as d; print(d('chopratejas/kompress-v2-base'))"
headroom proxy --port 18787 --anthropic-api-url http://127.0.0.1:9 > /tmp/warmup.log 2>&1 &
pid=$!
for i in $(seq 60); do curl -sf localhost:18787/health >/dev/null && break; sleep 1; done
python3 - <<'PY'
import json, urllib.request
blob = "\n".join(f"line {i}: INFO request handled in {i % 97} ms path=/api/admin/runs status=200" for i in range(4000))
body = {"model": "claude-sonnet-5-5", "max_tokens": 16, "messages": [
  {"role": "user", "content": "run tests"},
  {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "pnpm test"}}]},
  {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": blob}]}]}
req = urllib.request.Request("http://localhost:18787/v1/messages", json.dumps(body).encode(),
  {"content-type": "application/json", "x-api-key": "warmup", "anthropic-version": "2023-06-01"})
try: urllib.request.urlopen(req, timeout=300)
except Exception as e: print("warmup request:", type(e).__name__)
PY
sleep 5
kill $pid 2>/dev/null; wait $pid 2>/dev/null
tail -20 /tmp/warmup.log
du -sh "${HF_HOME:-$HOME/.cache/huggingface}"
! find "${HF_HOME:-$HOME/.cache/huggingface}" -name '*.incomplete' | grep .
