#!/usr/bin/env bash
# Submit a batch job when needed: bash run_apptainer_lumi.sh main.py [arguments...]
set -euo pipefail

# Slurm executes a spooled copy. Export the checkout path for automatic
# submission, and also support direct sbatch calls from the checkout.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_DIR="${PANDORA_REPO_DIR:-}"
if [[ -z "$REPO_DIR" ]]; then
    for candidate in "$SCRIPT_DIR" "${SLURM_SUBMIT_DIR:-}" "$PWD"; do
        if [[ -n "$candidate" && -f "$candidate/main.py" && -d "$candidate/src/pandora" ]]; then
            REPO_DIR="$candidate"
            break
        fi
    done
fi
if [[ -z "$REPO_DIR" || ! -d "$REPO_DIR" ]]; then
    echo "Cannot locate the Pandora checkout. Set PANDORA_REPO_DIR to its absolute path before submission." >&2
    exit 1
fi
REPO_DIR="$(CDPATH= cd -- "$REPO_DIR" && pwd)"
export PANDORA_REPO_DIR="$REPO_DIR"
IMAGE="${PANDORA_IMAGE:-$REPO_DIR/apptainer/images/pandora.sif}"
if [[ $# -eq 0 ]]; then
    echo "Usage: $0 script.py [arguments...]" >&2
    exit 2
fi
if [[ ! -f "$IMAGE" ]]; then
    echo "Container image not found: $IMAGE (override with PANDORA_IMAGE)" >&2
    exit 1
fi
for helper in cluster_util.sh slurm_node.sh run_node.sh; do
    if [[ ! -r "$REPO_DIR/apptainer/$helper" ]]; then
        echo "Missing launcher helper: $REPO_DIR/apptainer/$helper" >&2
        echo "Copy all three helper scripts from the updated repository into $REPO_DIR/apptainer/." >&2
        exit 1
    fi
done
command -v singularity >/dev/null
command -v srun >/dev/null
source "$REPO_DIR/apptainer/cluster_util.sh"
parse_cluster_resources "$@"
if [[ -z ${SLURM_JOB_ID:-} ]]; then
    if [[ ${PANDORA_BATCH_SUBMITTED:-} == 1 ]]; then
        echo "sbatch did not provide SLURM_JOB_ID; cannot start Pandora." >&2
        exit 1
    fi
    command -v sbatch >/dev/null
    # Override the default account for another LUMI project.
    ACCOUNT="${PANDORA_ACCOUNT:-${SLURM_ACCOUNT:-project_462001731}}"
    # LUMI's small partition supports at most four nodes.
    PARTITION=small
    if ((NODES > 4)); then PARTITION=standard; fi
    export PANDORA_DATA_ROOT="${PANDORA_DATA_ROOT:-${SCRATCH:-/scratch/$ACCOUNT/$USER/pandora-db}}"
    export PANDORA_BATCH_SUBMITTED=1
    LOG_DIR="${PANDORA_LOG_DIR:-$REPO_DIR/container_outputs}"
    mkdir -p "$LOG_DIR"
    LOG_DIR="$(CDPATH= cd -- "$LOG_DIR" && pwd)"
    # Resolve an image override before changing the batch working directory.
    export PANDORA_IMAGE="$(CDPATH= cd -- "$(dirname -- "$IMAGE")" && pwd)/$(basename -- "$IMAGE")"
    echo "Submitting Pandora for account $ACCOUNT. Nodes: $NODES; workers per node: $WORKERS. Logs: $LOG_DIR/pandora-%j.out"
    exec sbatch --job-name=pandora --export=ALL --chdir="$REPO_DIR" \
        --output="$LOG_DIR/pandora-%j.out" --error="$LOG_DIR/pandora-%j.err" --account="$ACCOUNT" --partition="${PANDORA_PARTITION:-$PARTITION}" \
        --nodes="$NODES" --ntasks="$NODES" --ntasks-per-node=1 --cpus-per-task="$CPUS" \
        --mem="${PANDORA_MEM:-8G}" --time="${PANDORA_TIME:-00:30:00}" \
        "$REPO_DIR/run_apptainer_lumi.sh" "$@"
fi

# Use the user's LUMI scratch directory, or an explicitly chosen writable path.
DATA_ROOT="${PANDORA_DATA_ROOT:-${SCRATCH:-}}"
if [[ -z "$DATA_ROOT" ]]; then
    echo "Set PANDORA_DATA_ROOT to a writable directory on your project's scratch storage." >&2
    exit 1
fi
mkdir -p "$DATA_ROOT"
RUN_DIR="$(mktemp -d "$DATA_ROOT/pandora-${SLURM_JOB_ID}.XXXXXX")"
RUN_DIR="$(CDPATH= cd -- "$RUN_DIR" && pwd)"
echo "Pandora database and logs: $RUN_DIR/node-<id>"
launch_cluster_nodes singularity "$@"
