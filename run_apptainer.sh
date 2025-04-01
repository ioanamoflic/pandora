
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

psql -U $USER -d $DB_NAME -p $PORT -c \"alter system set shared_buffers = '400GB';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"alter system set work_mem = '64MB';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"alter system set maintenance_work_mem = '4GB';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"alter system set checkpoint_completion_target = '0.9';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"alter system set checkpoint_timeout = '3600s';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"alter system set wal_buffers = '1GB';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"alter system set max_wal_size = '32GB';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"alter system set wal_writer_delay = '10ms';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"alter system set synchronous_commit = 'off';\"
psql -U $USER -d $DB_NAME -p $PORT -c \"alter system set autovacuum_naptime = '10s';\"


pg_ctl -o \"$INITDBPORT\" restart

psql -U $USER -d $DB_NAME -p $PORT -c \"show shared_buffers;\"
psql -U $USER -d $DB_NAME -p $PORT -c \"show work_mem;\"
psql -U $USER -d $DB_NAME -p $PORT -c \"show maintenance_work_mem;\"
psql -U $USER -d $DB_NAME -p $PORT -c \"show checkpoint_completion_target;\"
psql -U $USER -d $DB_NAME -p $PORT -c \"show checkpoint_timeout;\"
psql -U $USER -d $DB_NAME -p $PORT -c \"show max_wal_size;\"
psql -U $USER -d $DB_NAME -p $PORT -c \"show wal_buffers;\"
psql -U $USER -d $DB_NAME -p $PORT -c \"show wal_writer_delay;\"
psql -U $USER -d $DB_NAME -p $PORT -c \"show synchronous_commit;\"
psql -U $USER -d $DB_NAME -p $PORT -c \"show autovacuum_naptime;\"

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
