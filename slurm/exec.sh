mkdir -p /tmp/$SLURM_JOBID/pgdata /tmp/$SLURM_JOBID/pgrun

export EXEC="pg_ctl init && echo 'host all all 0.0.0.0/0 trust'>> /var/lib/postgresql/data/pg_hba.conf && pg_ctl start && export PYTHONPATH=$PYTHONPATH:/pandora && cd /pandora && python3.10 benchmarking/benchmark_db.py"

apptainer exec -B /tmp/$SLURM_JOBID/pgdata:/var/lib/postgresql/data -B /tmp/$SLURM_JOBID/pgrun:/var/run/postgresql -e -C  pandora.sif bash -c "$EXEC"

rm -rf /tmp/$SLURM_JOBID/pgdata /tmp/$SLURM_JOBID/pgrun
