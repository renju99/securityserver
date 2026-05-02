#!/usr/bin/env bash
# Sample probes for a *virtual* ZKTeco terminal serial (SN). No physical device required.
#
# Usage:
#   ./scripts/zkteco-virtual-device-sample.sh                    # defaults below
#   ./scripts/zkteco-virtual-device-sample.sh https://hr.example.com VIRTUAL-ZK-0001
#
# Paths:
#   - Through nginx (typical prod): BASE should include /api for HR, but iClock is at /iclock (not under /api).
#   - Direct API port 3000: BASE=http://127.0.0.1:3000  (no /api prefix on HR routes in Express).

set -euo pipefail

BASE="${1:-http://127.0.0.1:3000}"
SN="${2:-VIRTUAL-ZK-0001}"

echo "== ZKTeco virtual device sample (SN=$SN) against BASE=$BASE"
echo ""

echo "-- 1) iClock ping (plain OK from server)"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "${BASE%/}/iclock/ping" || true
curl -sS "${BASE%/}/iclock/ping" | head -c 200
echo ""
echo ""

echo "-- 2) getrequest (ZK device check GET; virtual SN in query)"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "${BASE%/}/iclock/getrequest?SN=${SN}" || true
curl -sS "${BASE%/}/iclock/getrequest?SN=${SN}" | head -c 200
echo ""
echo ""

echo "-- 3) cdata ATTLOG (empty body still returns OK; ingest only if device_key is registered in HR)"
curl -sS -X POST -o /dev/null -w "HTTP %{http_code}\n" \
  "${BASE%/}/iclock/cdata?SN=${SN}&table=ATTLOG" \
  -H 'Content-Type: text/plain' \
  --data-binary '' || true
echo ""

echo "Register the same SN as device_key in HR (ZKTeco ADMS preset), then repeat (3) with a real ATTLOG line to see punches in Biometric logs."
echo "HR wizard connection test (requires JWT): POST .../hr/biometrics/devices/connection-test with body type ZKTeco_ADMS."
