#!/bin/bash

#SBATCH --job-name="2048_1"
#SBATCH --partition=small
#SBATCH --account project_462000921
#SBATCH -o one_block_rsa2048/rsa_cont_1.out
#SBATCH --mem=20G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=65:00:00


bash run_apptainer_lumi.sh main.py lumi_config.json rsa 2048 1 0 1
# bash run_collect_lumi.sh lumi_config.json