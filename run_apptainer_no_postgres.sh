# Outside of Slurm use the PROCESSID and save it for later reference
# Use $PORT for the postgre port
SLURM_JOBID=$$
RED='\033[0;31m'
NC='\033[0m' # No Color
echo -e "${RED}$SLURM_JOBID <- $@ ${NC}"

# This is the script to run in the Pandora Apptainer
SCRIPTTORUN="
export PYTHONPATH=$PYTHONPATH:/pandora/src:/pandora

cd /pandora

python3 $@
bash
"

# Run Pandora in the apptainer
export EXEC="apptainer exec -B $(pwd):/pandora -e -C apptainer/images/pandora_new.sif"
$EXEC bash -c "$SCRIPTTORUN"
