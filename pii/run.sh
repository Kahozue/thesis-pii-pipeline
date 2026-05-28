#!/usr/bin/env bash
set -euo pipefail

# ── cleanup on any exit ──────────────────────────────────────────────────────
_cleanup() {
    echo ""
    echo "[run.sh] shutting down..."
    # kill all children in this process group
    jobs -p | xargs -r kill 2>/dev/null || true
    wait 2>/dev/null || true
    echo "[run.sh] done — all child processes terminated"
}
trap _cleanup EXIT INT TERM

# ── usage ────────────────────────────────────────────────────────────────────
PORT="${1:-8502}"
SCRIPT="${2:-app.py}"

echo "[run.sh] starting streamlit on port ${PORT} (script: ${SCRIPT})"
echo "[run.sh] press Ctrl+C to stop cleanly"
echo ""

# exec replaces this shell; trap still fires on EXIT
streamlit run "${SCRIPT}" --server.port "${PORT}" --server.headless true &
ST_PID=$!
wait "${ST_PID}"
