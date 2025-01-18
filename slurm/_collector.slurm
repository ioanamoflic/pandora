#!/bin/bash
#SBATCH --time=1:00:00
#SBATCH --mem=2gb
#SBATCH -N 1
#SBATCH --ntasks-per-node=1 
#SBATCH --job-name=collector
#SBATCH -e collector_%j.err
#SBATCH -o collector_%j.out

#SBATCH --constraint=localdisk
#SBATCH --signal=B:SIGINT@60
#SBATCH -p batch-hsw

srun bash ./collect.sh
