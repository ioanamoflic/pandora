#!/bin/bash
#SBATCH --time=1:00:00
#SBATCH --mem=8gb
#SBATCH -N 1
#SBATCH -n 10
#SBATCH --job-name=postgres_server
#SBATCH -e postgres_server_%j.err
#SBATCH -o postgres_server_%j.out
# SBATCH --licenses=common
# SBATCH --dependency=singleton
# SBATCH --signal=B:SIGINT@60

#export COMMON=$HOME/lustre/quansim_1-dsg0j0wqqk8/users/$USER
#export POSTGRES_HOME=$COMMON/postgres
#export POSTGRES_PASSWORD_FILE=$POSTGRES_HOME/config/postgres-password
#export PGPASSWORD="1234"
#export POSTGRES_USER=$USER
#export POSTGRES_DB=postgres
#export PGDATA=$POSTGRES_HOME/db/data
#export POSTGRES_HOST_AUTH_METHOD=md5
#export POSTGRES_INITDB_ARGS="--data-checksums"
#export POSTGRES_PORT=$(shuf -i 2000-65000 -n 1)

#module load PostgreSQL/14.4-GCCcore-11.3.0  Python/3.10.4-GCCcore-11.3.0


#module loadsingularity

mkdir -p pgdata pgrun
export EXEC="apptainer exec -B pgdata:/var/lib/postgresql/data -B pgrun:/var/run/postgresql -e -C  pandora.sif "

#$EXEC  pg_ctl init 
#$EXEC  pg_ctl start 
#$EXEC  export PYTHONPATH="$PYTHONPATH:/pandora"
#$EXEC /pandora/python3.10 benchmarking/benchmark_db.py


$EXEC bash -c "pg_ctl init && echo 'host all all 0.0.0.0/0 trust'>> /var/lib/postgresql/data/pg_hba.conf && pg_ctl start && export PYTHONPATH=$PYTHONPATH:/pandora && cd /pandora && python3.10 benchmarking/benchmark_db.py"


#appaitner run -B $POSTGRES_HOME/db:/var/lib/postgresql -B $POSTGRES_HOME/run:/var/run/postgresql docker://postgres:11 -c "port=$POSTGRES_PORT"

# database="postgres",
# user="postgres",
# host="localhost",
# port=5432,
# password="1234")
#

#mkdir -p $POSTGRES_HOME/config

#echo `hostname`:5432:postgres:$POSTGRES_USER:1234">>$POSTGRES_PASSWORD_FILE 

#initdb -D $PGDATA  
#pg_ctl -D $PGDATA start

#echo "Postgres server running on $(hostname) on port $POSTGRES_PORT"
#echo "This job started at $(date +%Y-%m-%dT%T)"
#echo "This job will end at $(squeue --noheader -j $SLURM_JOBID -o %e) (in $(squeue --noheader -j $SLURM_JOBID -o %L))"
#echo "Postgres server running on $(hostname) on port $POSTGRES_PORT"

#pg_ctl -D $PGDATA -l logfile status 

#postgres -i -T -d3 -W -p $POSTGRES_PORT  -D $PGDATA  -h localhost
#export COMMON=$HOME/lustre/quansim_1-dsg0j0wqqk8/users/$USER
#export POSTGRES_HOME=$COMMON/postgres
#export POSTGRES_PASSWORD_FILE=$POSTGRES_HOME/config/postgres-password
#export PGPASSWORD="1234"
#echo $POSTGRES_USER
#echo $POSTGRES_DB=
#echo $PGDATA=
#echo $POSTGRES_HOST_AUTH_METHOD
#echo $POSTGRES_INITDB_ARGS
#echo $POSTGRES_PORT
