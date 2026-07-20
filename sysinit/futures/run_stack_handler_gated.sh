#!/usr/bin/env bash
# Gated launcher for the rob_dynamic stack handler.
#
# Fixes two operational gaps found on the first auto-cycle (2026-07-20): the handler fired on a FIXED
# 00:30 offset BEFORE (a) the daily refresh had finished staging the book (~45 min) and (b) IB Gateway
# was up -> it failed clean and left a stale process lock. This launcher waits for BOTH preconditions,
# then execs the canonical run_stack_handler. Pointed at by pst-rob-stackhandler.service.
# Additive; calls no core code directly (just the same run_stack_handler entrypoint). See notes/SESSION_HANDOFF.md.
set -uo pipefail
cd /home/andrew/pysystemtrade || exit 1
export TZ=UTC
GW_HOST=127.0.0.1; GW_PORT=4002
REFRESH=pst-rob-refresh.service
REFRESH_WAIT=120   # x30s = up to 60 min for the refresh to finish
GW_WAIT=30         # x30s = up to 15 min for IB Gateway
log(){ echo "[gated-stackhandler $(date -u '+%H:%M:%S UTC')] $*"; }

# --- 1. wait for TODAY's refresh to finish CLEANLY (it stages the book) ---
today=$(date -u +%Y-%m-%d)
log "waiting for today's $REFRESH to finish cleanly (up to 60 min)..."
ok=0
for i in $(seq 1 $REFRESH_WAIT); do
  st=$(systemctl --user is-active "$REFRESH" 2>/dev/null)
  if [ "$st" != "active" ] && [ "$st" != "activating" ] && [ "$st" != "reloading" ]; then
    rc=$(systemctl --user show "$REFRESH" -p ExecMainStatus --value 2>/dev/null)
    ets=$(systemctl --user show "$REFRESH" -p ExecMainExitTimestamp --value 2>/dev/null)
    ed=$(date -u -d "$ets" +%Y-%m-%d 2>/dev/null || true)
    if [ "$rc" = "0" ] && [ "$ed" = "$today" ]; then ok=1; break; fi
  fi
  sleep 30
done
if [ "$ok" != "1" ]; then
  log "today's refresh did not finish cleanly within 60 min -> NOT starting handler (protects against trading a half-built/stale book)"; exit 1
fi
log "refresh finished cleanly."

# --- 2. wait for IB Gateway to be reachable ---
log "waiting for IB Gateway ${GW_HOST}:${GW_PORT} (up to 15 min)..."
up=0
for i in $(seq 1 $GW_WAIT); do
  if timeout 2 bash -c "exec 3<>/dev/tcp/${GW_HOST}/${GW_PORT}" 2>/dev/null; then up=1; break; fi
  sleep 30
done
if [ "$up" != "1" ]; then
  log "IB Gateway not up after ~15 min -> NOT starting handler. Rerun once Gateway is up: systemctl --user start pst-rob-stackhandler.service"; exit 1
fi
log "Gateway up -> starting canonical run_stack_handler."

# --- 3. hand off (exec so systemd tracks the handler as the service's main process) ---
exec /home/andrew/.local/bin/uv run python -m sysproduction.run_stack_handler
