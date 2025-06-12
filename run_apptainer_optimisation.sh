
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
fi


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
export EXEC="apptainer exec -B $PGDATA:/var/lib/postgresql/data -B $PGRUN:/var/run/postgresql -B $(pwd):/pandora -e -C apptainer/images/pandora_new.sif"
$EXEC bash -c "$SCRIPTTORUN"

