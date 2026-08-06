#!/usr/bin/env bash
#
# Start the dashboard locally: FastAPI backend + Next.js frontend.
#
#   ./run.sh          install anything missing, then start both servers
#   ./run.sh --no-install   skip dependency installation (faster restarts)
#
# Open http://localhost:3000 once it reports ready. Ctrl-C stops both.

set -euo pipefail

cd "$(dirname "$0")"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
PYTHON="${PYTHON:-python3}"
INSTALL=1

for arg in "$@"; do
  case "$arg" in
    --no-install) INSTALL=0 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '\033[36m[run]\033[0m %s\n' "$1"; }
err() { printf '\033[31m[run]\033[0m %s\n' "$1" >&2; }

command -v "$PYTHON" >/dev/null || { err "$PYTHON not found"; exit 1; }
command -v npm >/dev/null || { err "npm not found - install Node.js 20+"; exit 1; }

# A port left occupied by a previous run is the most common startup failure, and
# uvicorn/next report it in ways that don't obviously say "something else is here".
for port in "$API_PORT" "$WEB_PORT"; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    exec 3<&- 3>&-
    err "port $port is already in use - stop that process, or set API_PORT/WEB_PORT"
    exit 1
  fi
done

if [ ! -f .env ]; then
  log "no .env found - creating one from example.env"
  cp example.env .env
  err "Edit .env and add your GEMINI_API_KEY before generating videos."
  err "The dashboard still starts without it; set it there under Settings."
fi

if [ "$INSTALL" -eq 1 ]; then
  log "installing backend dependencies"
  "$PYTHON" -m pip install --quiet --disable-pip-version-check -r api/requirements.txt

  if [ ! -d web/node_modules ]; then
    log "installing frontend dependencies (first run - this takes a minute)"
    (cd web && npm install --no-audit --no-fund)
  fi
fi

API_PID=""
WEB_PID=""

cleanup() {
  trap - INT TERM EXIT
  log "shutting down"
  # Kill the process groups: npm doesn't forward signals to the next-server it
  # spawns, so signalling the npm wrapper alone leaves the port bound.
  for pid in "$WEB_PID" "$API_PID"; do
    [ -n "$pid" ] && kill -- "-$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

log "starting API on http://localhost:$API_PORT"
set -m
"$PYTHON" -m uvicorn api.main:app --port "$API_PORT" --reload &
API_PID=$!
set +m

# Wait for the API to answer before starting the frontend, so the dashboard's
# first render finds a live backend instead of flashing "disconnected".
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:$API_PORT/api/health" >/dev/null 2>&1; then
    log "API ready"
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    err "API failed to start - see the traceback above"
    exit 1
  fi
  sleep 1
done

log "starting web on http://localhost:$WEB_PORT"
# Default the browser to calling the API directly. Note ${VAR-default}, not
# ${VAR:-default}: an explicitly empty NEXT_PUBLIC_API_URL is meaningful (it
# selects same-origin URLs proxied by Next, which is how the devcontainer runs
# this) and must survive rather than being replaced by the default.
API_URL="${NEXT_PUBLIC_API_URL-http://localhost:$API_PORT}"
set -m
(cd web && NEXT_PUBLIC_API_URL="$API_URL" API_PROXY_TARGET="http://localhost:$API_PORT" \
  npm run dev -- --port "$WEB_PORT") &
WEB_PID=$!
set +m

for _ in $(seq 1 90); do
  if curl -sf -o /dev/null "http://127.0.0.1:$WEB_PORT/" 2>/dev/null; then
    log "ready -> http://localhost:$WEB_PORT"
    break
  fi
  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    err "web server failed to start - see the output above"
    exit 1
  fi
  sleep 1
done

# Exit as soon as either server dies, rather than leaving a half-up stack.
wait -n "$API_PID" "$WEB_PID"
