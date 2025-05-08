
# Check if the first file is a json config
INITDBPORT=""
if [[ $2 == *json ]]
then
    # Read the port number from JSON config
    PYTHONPORT="import json;file=open('$2', 'r');print(json.load(file)['port'])"
    PYTHON_USER="import json;file=open('$2', 'r');print(json.load(file)['user'])"
    PYTHON_DB_NAME="import json;file=open('$2', 'r');print(json.load(file)['database'])"
    PORT=$(echo $PYTHONPORT | python3)
    USER=$(echo $PYTHON_USER | python3)
    DB_NAME=$(echo $PYTHON_DB_NAME | python3)

    INITDBPORT="-p $PORT"

    # shift the parameters of the script effectively pop-ing $1?
    # https://stackoverflow.com/a/9057699
    # shift
fi

# Outside of Slurm use the PROCESSID and save it for later reference
# Use $PORT for the postgre port
SLURM_JOBID=$$
RED='\033[0;31m'
NC='\033[0m' # No Color
echo -e "${RED}$SLURM_JOBID <- $@ ${NC}"
echo "$@" >> trace_$SLURM_JOBID.txt

# This is the script to run in the Pandora Apptainer
SCRIPTTORUN="
pg_ctl init
echo 'host all all 0.0.0.0/0 trust'>> /var/lib/postgresql/data/pg_hba.conf

pg_ctl -o \"$INITDBPORT\" start

# memory
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET shared_buffers = '512GB';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET work_mem = '64MB';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET maintenance_work_mem = '16GB';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET effective_cache_size = '1200GB';\"

# wal
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET wal_buffers = '512MB';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET wal_writer_delay = '5ms';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET commit_delay = '0';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET commit_siblings = '5';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET synchronous_commit = 'off';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET fsync = 'on';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET full_page_writes = 'off';\"

# checkpoint
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET checkpoint_timeout = '30min';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET checkpoint_completion_target = '0.9';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET max_wal_size = '128GB';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET min_wal_size = '32GB';\"

# autovacuum
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET autovacuum = 'on';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET autovacuum_max_workers = '64';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET autovacuum_naptime = '2s';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET autovacuum_vacuum_cost_limit = '8000';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET autovacuum_vacuum_cost_delay = '1ms';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET autovacuum_vacuum_threshold = '100';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET autovacuum_vacuum_scale_factor = '0.005';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET autovacuum_vacuum_insert_threshold = '1000';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET autovacuum_vacuum_insert_scale_factor = '0.01';\"

# workers
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET max_connections = '512';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET superuser_reserved_connections = '10';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET max_worker_processes = '192';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET max_parallel_workers = '128';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET max_parallel_workers_per_gather = '16';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET parallel_leader_participation = 'on';\"

# locks
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET max_locks_per_transaction = '256';\"

# i/o
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET effective_io_concurrency = '512';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET random_page_cost = '1.0';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET track_io_timing = 'on';\"

# logging
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET log_checkpoints = 'on';\"

# temp
psql -U $USER -d $DB_NAME -p $PORT -c \"ALTER SYSTEM SET temp_buffers = '64MB';\"


pg_ctl -o \"$INITDBPORT\" restart

export PYTHONPATH=$PYTHONPATH:/pandora/src:/pandora

cd /pandora

python3 $@
bash
"

# Create the local storage of a Pandora
PGDATA="/tmp/$SLURM_JOBID/pgdata"+
rm -rf $PGDATA
PGRUN="/tmp/$SLURM_JOBID/pgrun"
rm -rf $PGRUN
mkdir -p $PGDATA $PGRUN

# Run Pandora in the apptainer
export EXEC="apptainer exec -B $PGDATA:/var/lib/postgresql/data -B $PGRUN:/var/run/postgresql -B $(pwd):/pandora -e -C apptainer/images/pandora.sif"
$EXEC bash -c "$SCRIPTTORUN"

# Do not delete, we want to keep the circuit databases for later
# rm -irf $PGDATA $PGRUN

# apptainer exec -B $(pwd):/pandora -e -C apptainer/images/pandora.sif bash -c "$SCRIPTTORUN"
