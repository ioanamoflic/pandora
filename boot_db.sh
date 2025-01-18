RED='\033[0;31m'
NC='\033[0m' # No Color

if [ "$#" -ne 2 ]; then
    echo -e "${RED}run_boot.sh [PROCESSID -- get it from trace*.txt] and [CONFIG.json]"
    exit 0
fi


# Check if the first file is a json config
INITDBPORT=""
if [[ $2 == *json ]]
then
    # Read the port number from JSON config
    PYTHONPORT="import json;file=open('$2', 'r');print(json.load(file)['port'])"
    PORT=$(echo $PYTHONPORT | python3)
    INITDBPORT="-p $PORT"
fi

# Outside of Slurm use the PROCESSID and save it for later reference
# Use $PORT for the postgre port
SLURM_JOBID=$1
echo -e "${RED}$SLURM_JOBID <- $@ ${NC}"

# This is the script to run in the Pandora Apptainer
SCRIPTTORUN="
pg_ctl -o \"$INITDBPORT\" start
psql -p $PORT -d postgres
"

# Create the local storage of a Pandora
PGDATA="/tmp/$SLURM_JOBID/pgdata"
PGRUN="/tmp/$SLURM_JOBID/pgrun"

# Run Pandora in the apptainer
export EXEC="apptainer exec -B $PGDATA:/var/lib/postgresql/data -B $PGRUN:/var/run/postgresql -B $(pwd):/pandora -e -C apptainer/images/pandora.sif"
$EXEC bash -c "$SCRIPTTORUN"
