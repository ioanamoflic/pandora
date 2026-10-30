#!/usr/bin/env bash
# Run inside a Slurm allocation: bash run_apptainer_toubkal.sh main.py [arguments...]
set -euo pipefail

REPO_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
IMAGE="${PANDORA_IMAGE:-$REPO_DIR/apptainer/images/pandora.sif}"
if [[ $# -eq 0 ]]; then
    echo "Usage: $0 script.py [arguments...]" >&2
    exit 2
fi
if [[ ! -f "$IMAGE" ]]; then
    echo "Container image not found: $IMAGE (override with PANDORA_IMAGE)" >&2
    exit 1
fi
# Prefer Apptainer; allow installations exposing the compatible Singularity CLI.
if command -v apptainer >/dev/null; then
    CONTAINER_RUNTIME=apptainer
elif command -v singularity >/dev/null; then
    CONTAINER_RUNTIME=singularity
else
    echo "Load your cluster's Apptainer module before running this launcher." >&2
    exit 1
fi
for helper in cluster_util.sh slurm_node.sh run_node.sh; do
    if [[ ! -r "$REPO_DIR/apptainer/$helper" ]]; then
        echo "Missing launcher helper: $REPO_DIR/apptainer/$helper" >&2
        echo "Copy apptainer/cluster_util.sh, apptainer/slurm_node.sh, and apptainer/run_node.sh from the updated repository to the cluster." >&2
        exit 1
    fi
done
command -v srun >/dev/null
source "$REPO_DIR/apptainer/cluster_util.sh"
parse_cluster_resources "$@"
if [[ -z ${SLURM_JOB_ID:-} ]]; then
    echo "Run this launcher inside an sbatch job or salloc allocation." >&2
    exit 1
fi

# Configure storage without assuming a Toubkal project directory layout.
DATA_ROOT="${PANDORA_DATA_ROOT:-${SCRATCH:-}}"
if [[ -z "$DATA_ROOT" ]]; then
    echo "Set PANDORA_DATA_ROOT to a writable directory on your project's scratch storage." >&2
    exit 1
fi
mkdir -p "$DATA_ROOT"
RUN_DIR="$(mktemp -d "$DATA_ROOT/pandora-${SLURM_JOB_ID}.XXXXXX")"
RUN_DIR="$(CDPATH= cd -- "$RUN_DIR" && pwd)"
echo "Pandora database and logs: $RUN_DIR/node-<id>"
launch_cluster_nodes "$CONTAINER_RUNTIME" "$@"
