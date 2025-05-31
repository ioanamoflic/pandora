#!/bin/bash

#SBATCH --job-name="rsa_cont_1"
#SBATCH --partition=small
#SBATCH --account project_462000921
#SBATCH -o container_outputs/rsa_cont_1.out
#SBATCH --mem=30G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --time=24:00:00


bash run_apptainer.sh main.py lumi_config.json rsa 64 1
