SCRIPTTORUN="
pg_ctl init
echo 'host all all 0.0.0.0/0 trust'>> /var/lib/postgresql/data/pg_hba.conf

pg_ctl start

export PYTHONPATH=$PYTHONPATH:/pandora

cd /pandora

python3 $@
"

apptainer exec -B $(pwd):/pandora -e -C apptainer/images/pandora.sif bash -c "$SCRIPTTORUN"
