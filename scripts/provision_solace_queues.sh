#!/usr/bin/env bash
# provision_solace_queues.sh
# Creates the Flink consumer queue and monitoring fanout queue in Solace PubSub+.
# Run once after `docker compose up -d` and before starting the pipeline.
#
# Usage:
#   ./scripts/provision_solace_queues.sh
#   SOLACE_HOST=http://my-solace:8080 SOLACE_PASS=secret ./scripts/provision_solace_queues.sh

set -euo pipefail

SOLACE_HOST="${SOLACE_HOST:-http://localhost:8080}"
SOLACE_USER="${SOLACE_USER:-admin}"
SOLACE_PASS="${SOLACE_PASS:-admin}"
VPN="${SOLACE_VPN:-default}"
BASE="${SOLACE_HOST}/SEMP/v2/config/msgVpns/${VPN}"
AUTH="-u ${SOLACE_USER}:${SOLACE_PASS}"
TOPIC="aircraft/engine/*/telemetry/cycle"

echo "==> Provisioning Solace queues on ${SOLACE_HOST} (VPN: ${VPN})"

# ── Wait for Solace to be ready ───────────────────────────────────────────────
echo "--> Waiting for Solace SEMP API..."
for i in $(seq 1 30); do
  if curl -sf "${SOLACE_HOST}/SEMP/v2/config" ${AUTH} -o /dev/null 2>&1; then
    echo "    Solace is ready."
    break
  fi
  echo "    Attempt ${i}/30 — retrying in 5s..."
  sleep 5
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Solace did not become ready in time." >&2
    exit 1
  fi
done

# ── Helper: create queue (idempotent — ignores 400 if already exists) ─────────
create_queue() {
  local name="$1"
  local access_type="$2"
  local extra="${3:-}"

  echo "--> Creating queue: ${name} (${access_type})"
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE}/queues" ${AUTH} \
    -H "Content-Type: application/json" \
    -d "{
      \"queueName\": \"${name}\",
      \"accessType\": \"${access_type}\",
      \"permission\": \"consume\",
      \"ingressEnabled\": true,
      \"egressEnabled\": true,
      \"maxMsgSpoolUsage\": 512,
      \"maxTtl\": 60,
      \"respectTtlEnabled\": true,
      \"replayStartLocation\": \"beginning\"
      ${extra}
    }")

  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "400" ]; then
    echo "    Queue '${name}': OK (HTTP ${HTTP_CODE})"
  else
    echo "    WARNING: Unexpected HTTP ${HTTP_CODE} for queue '${name}'"
  fi
}

# ── Helper: bind subscription to queue (idempotent) ──────────────────────────
bind_subscription() {
  local queue="$1"
  local topic="$2"

  echo "--> Binding subscription '${topic}' → queue '${queue}'"
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "${BASE}/queues/${queue}/subscriptions" ${AUTH} \
    -H "Content-Type: application/json" \
    -d "{\"subscriptionTopic\": \"${topic}\"}")

  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "400" ]; then
    echo "    Subscription: OK (HTTP ${HTTP_CODE})"
  else
    echo "    WARNING: Unexpected HTTP ${HTTP_CODE} for subscription on '${queue}'"
  fi
}

# ── 1. Flink / standalone consumer queue (exclusive, partitioned) ─────────────
create_queue "flink.feature.processor" "exclusive" \
  ",\"partitionCount\": 8, \"partitionRebalanceDelay\": 5, \"partitionRebalanceMaxHandoffTime\": 10"
bind_subscription "flink.feature.processor" "${TOPIC}"

# ── 2. Monitoring fanout queue (non-exclusive broadcast) ─────────────────────
create_queue "monitoring.telemetry.fanout" "non-exclusive"
bind_subscription "monitoring.telemetry.fanout" "${TOPIC}"

echo ""
echo "==> Done. Queues provisioned:"
echo "    flink.feature.processor   — exclusive, partitioned (8), for Flink/consumer"
echo "    monitoring.telemetry.fanout — non-exclusive, for monitoring/broadcast"
echo ""
echo "    Verify in Solace Manager: ${SOLACE_HOST}"
