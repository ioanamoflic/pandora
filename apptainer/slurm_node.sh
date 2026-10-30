#!/usr/bin/env bash
# Executed by srun once per node, before entering the container.
set -euo pipefail
RUNTIME="$1"
REPO_DIR="$2"
IMAGE="$3"
RUN_DIR="$4"
NODES="$5"
WORKERS="$6"
DB_USER="$7"
shift 7
NODE_ID="${SLURM_PROCID:?srun must set SLURM_PROCID}"
if [[ ! "$NODE_ID" =~ ^[0-9]+$ ]] || ((NODE_ID >= NODES)); then
    echo "Invalid node ID: $NODE_ID for $NODES nodes" >&2
    exit 2
fi
NODE_DIR="$RUN_DIR/node-$NODE_ID"
mkdir -p "$NODE_DIR/pgdata" "$NODE_DIR/pgrun"
echo "Node $NODE_ID/$NODES on $(hostname): $WORKERS workers; data: $NODE_DIR"
exec "$RUNTIME" exec --cleanenv --containall \
    --env "PANDORA_NODE_ID=$NODE_ID" --env "PANDORA_NODE_COUNT=$NODES" \
    --env "PANDORA_WORKER_COUNT=$WORKERS" \
    --bind "$REPO_DIR:/pandora" --bind "$NODE_DIR:/pandora-run" \
    "$IMAGE" bash /pandora/apptainer/run_node.sh "$DB_USER" "$@"
