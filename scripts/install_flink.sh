#!/usr/bin/env bash
# Install PyFlink 2.2.1 into the project venv.
#
# PyFlink requires:
#   1. A Flink binary distribution (provides the JARs)
#   2. The apache-flink Python package (thin client wrapper)
#
# The Python package alone is NOT enough — it needs FLINK_HOME pointing
# to a Flink installation that contains lib/ and opt/ JARs.
#
# For LOCAL DEVELOPMENT without a Flink cluster, use the standalone consumer:
#   python -m streaming.pipeline.standalone_consumer
#
# For PRODUCTION (Flink cluster via Docker Compose), run:
#   docker compose -f docker-compose.streaming.yml up -d
#   flink run -py streaming/pipeline/telemetry_pipeline.py --parallelism 4 -pyfs streaming/
#
# This script sets up the Python package + downloads Flink binaries.

set -e

FLINK_VERSION="2.2.1"
FLINK_SCALA="2.12"
FLINK_DIST_URL="https://archive.apache.org/dist/flink/flink-${FLINK_VERSION}/flink-${FLINK_VERSION}-bin-scala_${FLINK_SCALA}.tgz"
FLINK_HOME="${HOME}/.local/flink-${FLINK_VERSION}"

# ── 1. Install Python package ─────────────────────────────────────────────────
echo "[flink-install] Installing apache-flink==${FLINK_VERSION} Python package..."
uv pip install "apache-flink==${FLINK_VERSION}" --no-deps
uv pip install "py4j==0.10.9.7" "cloudpickle>=2.2.0" "ruamel.yaml>=0.17"

# ── 2. Download Flink binary distribution (provides JARs) ────────────────────
if [ ! -d "${FLINK_HOME}" ]; then
    echo "[flink-install] Downloading Flink ${FLINK_VERSION} binary distribution..."
    mkdir -p "$(dirname ${FLINK_HOME})"
    curl -L "${FLINK_DIST_URL}" | tar -xz -C "$(dirname ${FLINK_HOME})"
    mv "$(dirname ${FLINK_HOME})/flink-${FLINK_VERSION}" "${FLINK_HOME}"
    echo "[flink-install] Flink installed to ${FLINK_HOME}"
else
    echo "[flink-install] Flink binary already at ${FLINK_HOME}"
fi

# ── 3. Set FLINK_HOME and verify ─────────────────────────────────────────────
export FLINK_HOME
echo "[flink-install] Verifying PyFlink import with FLINK_HOME=${FLINK_HOME}..."
FLINK_HOME="${FLINK_HOME}" uv run python -c "
from pyflink.datastream import StreamExecutionEnvironment
print('[flink-install] OK — PyFlink ${FLINK_VERSION} is ready')
print('[flink-install] Add to your shell: export FLINK_HOME=${FLINK_HOME}')
"

echo ""
echo "Add this to your shell profile (~/.bashrc or ~/.zshrc):"
echo "  export FLINK_HOME=${FLINK_HOME}"
