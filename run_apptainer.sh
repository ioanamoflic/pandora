#!/usr/bin/env bash
set -eu

SLURM_JOBID=$$

RED='\033[0;31m'
NC='\033[0m'

echo -e "${RED}$SLURM_JOBID <- $@ ${NC}"
echo "$@" >> "trace_$SLURM_JOBID.txt"

# This is the script to run in the Pandora Apptainer
SCRIPTTORUN="
pg_ctl init
echo 'host all all 0.0.0.0/0 trust' >> /var/lib/postgresql/data/pg_hba.conf
pg_ctl start

export PYTHONPATH=$PYTHONPATH:/pandora/src:/pandora
cd /pandora

python3 $@
bash
"

# Create the local storage of Pandora
PGDATA="/tmp/$SLURM_JOBID/pgdata"
rm -rf "$PGDATA"

PGRUN="/tmp/$SLURM_JOBID/pgrun"
rm -rf "$PGRUN"

mkdir -p "$PGDATA" "$PGRUN"

# Run Pandora in the apptainer
export EXEC="apptainer exec \
    -B $PGDATA:/var/lib/postgresql/data \
    -B $PGRUN:/var/run/postgresql \
    -B $PGDATA:/var/lib/postgresql/18/docker \
    -B $(pwd):/pandora \
    -e -C apptainer/images/pandora.sif"

$EXEC bash -c "$SCRIPTTORUN" bash "$@"

# Do not delete, we want to keep the circuit databases for later
# rm -irf "$PGDATA" "$PGRUN"