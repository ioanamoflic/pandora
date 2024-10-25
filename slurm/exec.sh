PGDATA="/tmp/$SLURM_JOBID/pgdata"
PGRUN="/tmp/$SLURM_JOBID/pgrun"

mkdir -p $PGDATA $PGRUN

export EXEC="apptainer exec -B $PGDATA:/var/lib/postgresql/data -B $PGRUN:/var/run/postgresql -B pandora:/pandora -e -C pandora.sif"

$EXEC bash /pandora/slurm/execinapp.sh

rm -rf $PGDATA $PGRUN
