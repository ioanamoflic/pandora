#!/bin/bash
#SBATCH --time=1:00:00
#SBATCH --mem=2gb
#SBATCH -N 10
#SBATCH --ntasks-per-node=1 
#SBATCH --job-name=pandora
#SBATCH -e pandora_%j.err
#SBATCH -o pandora_%j.out
#SBATCH --dependency=singleton
#SBATCH --constraint=localdisk
#SBATCH --signal=B:SIGINT@60
#SBATCH -p batch-hsw
# SBATCH --exclusive

#export COMMON=$HOME/lustre/quansim_1-dsg0j0wqqk8/users/$USER/Pandora2024
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
#cd $COMMON

srun hostname -s | uniq > machinefile.txt
#module loadsingularity

srun bash ./exec.sh
