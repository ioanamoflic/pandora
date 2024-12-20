SCRIPTTORUN="
pg_ctl init
echo 'host all all 0.0.0.0/0 trust'>> /var/lib/postgresql/data/pg_hba.conf

pg_ctl start

export PYTHONPATH=$PYTHONPATH:/pandora/src:/pandora

cd /pandora

python3 $@
"

#Outside of Slurm use the processid and save it for later reference
SLURM_JOBID=$$
echo "$@" >> trace_$SLURM_JOBID.txt

# Local storage of a Pandora
PGDATA="/tmp/$SLURM_JOBID/pgdata"
PGRUN="/tmp/$SLURM_JOBID/pgrun"
mkdir -p $PGDATA $PGRUN

export EXEC="apptainer exec -B $PGDATA:/var/lib/postgresql/data -B $PGRUN:/var/run/postgresql -B $(pwd):/pandora -e -C apptainer/images/pandora.sif"

# run Pandora in the apptainer
$EXEC bash -c "$SCRIPTTORUN"

# Do not delete, we want to keep the circuit databases for later
#rm -rf $PGDATA $PGRUN

# apptainer exec -B $(pwd):/pandora -e -C apptainer/images/pandora.sif bash -c "$SCRIPTTORUN"
