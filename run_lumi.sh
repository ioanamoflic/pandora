#!/bin/bash

#SBATCH --job-name="collect"
#SBATCH --partition=small
#SBATCH --account project_462000921
#SBATCH -o container_outputs/collect.out
#SBATCH --mem=1G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=24:00:00


# bash run_apptainer_lumi.sh main.py lumi_config.json rsa 64 10
bash run_collect_lumi.sh lumi_config.json