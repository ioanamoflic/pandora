
# Check if the first file is a json config
INITDBPORT=""
if [[ $2 == *json ]]
then
    # Read the port number from JSON config
    PYTHONPORT="import json;file=open('$2', 'r');print(json.load(file)['port'])"
    PORT=$(echo $PYTHONPORT | python3)
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

export PYTHONPATH=$PYTHONPATH:/pandora/src:/pandora

cd /pandora

python3 $@
"


# Create the local storage of a Pandora
PGDATA="/tmp/$SLURM_JOBID/pgdata"
PGRUN="/tmp/$SLURM_JOBID/pgrun"
mkdir -p $PGDATA $PGRUN

# Run Pandora in the apptainer
export EXEC="apptainer exec -B $PGDATA:/var/lib/postgresql/data -B $PGRUN:/var/run/postgresql -B $(pwd):/pandora -e -C apptainer/images/pandora.sif"
$EXEC bash -c "$SCRIPTTORUN"

# Do not delete, we want to keep the circuit databases for later
rm -irf $PGDATA $PGRUN

# apptainer exec -B $(pwd):/pandora -e -C apptainer/images/pandora.sif bash -c "$SCRIPTTORUN"
