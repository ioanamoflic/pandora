#!/usr/bin/env bash
# Request an allocation when needed: bash run_apptainer_lumi.sh main.py [arguments...]
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
command -v singularity >/dev/null
command -v srun >/dev/null
if [[ -z ${SLURM_JOB_ID:-} ]]; then
    if [[ ${PANDORA_ALLOCATION_REQUESTED:-} == 1 ]]; then
        echo "salloc did not provide SLURM_JOB_ID; cannot start Pandora." >&2
        exit 1
    fi
    command -v salloc >/dev/null
    # Default account matches run_lumi.sh; override for another LUMI project.
    ACCOUNT="${PANDORA_ACCOUNT:-${SLURM_ACCOUNT:-project_462001731}}"
    WORKERS=1
    ARGS=("$@")
    for ((i=1; i<${#ARGS[@]}; i++)); do
        case "${ARGS[i]}" in
            --nproc)
                WORKERS="${ARGS[i+1]:-}"
                ;;
            --nproc=*)
                WORKERS="${ARGS[i]#--nproc=}"
                ;;
        esac
    done
    if [[ ! "$WORKERS" =~ ^[1-9][0-9]*$ ]]; then
        echo "--nproc must be a positive integer." >&2
        exit 2
    fi
    export PANDORA_DATA_ROOT="${PANDORA_DATA_ROOT:-${SCRATCH:-/scratch/$ACCOUNT/$USER/pandora-db}}"
    export PANDORA_ALLOCATION_REQUESTED=1
    echo "Requesting a Slurm allocation for account $ACCOUNT; waiting for resources..."
    exec salloc --account="$ACCOUNT" --partition="${PANDORA_PARTITION:-small}" \
        --nodes=1 --ntasks=1 --cpus-per-task="${PANDORA_CPUS:-$WORKERS}" \
        --mem="${PANDORA_MEM:-8G}" --time="${PANDORA_TIME:-00:30:00}" \
        bash "$REPO_DIR/run_apptainer_lumi.sh" "$@"
fi

# Use the user's LUMI scratch directory, or an explicitly chosen writable path.
DATA_ROOT="${PANDORA_DATA_ROOT:-${SCRATCH:-}}"
if [[ -z "$DATA_ROOT" ]]; then
    echo "Set PANDORA_DATA_ROOT to a writable directory on your project's scratch storage." >&2
    exit 1
fi
mkdir -p "$DATA_ROOT"
RUN_DIR="$(mktemp -d "$DATA_ROOT/pandora-${SLURM_JOB_ID}.XXXXXX")"
mkdir -p "$RUN_DIR/pgdata" "$RUN_DIR/pgrun"
echo "Pandora database and logs: $RUN_DIR"

# One container owns one PostgreSQL instance; Python controls worker processes.
srun --nodes=1 --ntasks=1 singularity exec --cleanenv --containall \
    --bind "$REPO_DIR:/pandora" \
    --bind "$RUN_DIR:/pandora-run" \
    "$IMAGE" bash -s -- "$(id -un)" "$@" <<'CONTAINER'
set -euo pipefail
DEFAULT_DB_USER="$1"
shift
export PYTHONPATH="/pandora/src:/pandora${PYTHONPATH:+:$PYTHONPATH}"
export PGDATA=/pandora-run/pgdata
cd /pandora

# Read main.py's optional config using the Python installed in the container.
# Keep arguments intact, including filenames containing spaces.
python3 - "$DEFAULT_DB_USER" "$@" > /pandora-run/db-settings <<'PY'
import json
import sys

config = {}
args = sys.argv[3:]
for i, arg in enumerate(args):
    if arg in ('-c', '--config'):
        if i + 1 == len(args):
            raise SystemExit('Missing config filename')
        with open(args[i + 1]) as stream:
            config = json.load(stream)
        break
    if arg.startswith('--config='):
        with open(arg.split('=', 1)[1]) as stream:
            config = json.load(stream)
        break
if config.get('host') not in (None, '', 'localhost', '127.0.0.1', '::1'):
    raise SystemExit('This launcher starts a local database; config host must be localhost.')
port = int(config.get('port') or 5432)
if not 1 <= port <= 65535:
    raise SystemExit('Invalid PostgreSQL port')
values = [str(port), config.get('user') or sys.argv[1], config.get('database') or 'postgres']
for value in values:
    if not isinstance(value, str) or any(c in value for c in '\n\r\0'):
        raise SystemExit('Invalid database configuration value')
    print(value)
PY
mapfile -t DB_SETTINGS < /pandora-run/db-settings
export PGPORT="${DB_SETTINGS[0]}"
export PGUSER="${DB_SETTINGS[1]}"
DB_NAME="${DB_SETTINGS[2]}"
export PGHOST=127.0.0.1

initdb -D "$PGDATA" -U "$PGUSER" --auth-local=trust --auth-host=trust
cleanup() {
    pg_ctl -D "$PGDATA" -m fast -w stop || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
pg_ctl -D "$PGDATA" -l /pandora-run/postgres.log \
    -o "-p $PGPORT -k /pandora-run/pgrun -h localhost" -w start
if [[ "$DB_NAME" != postgres && "$DB_NAME" != template0 && "$DB_NAME" != template1 ]]; then
    createdb -- "$DB_NAME"
fi
python3 "$@"
CONTAINER
