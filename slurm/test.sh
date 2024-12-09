#!/usr/bin/bash

for i in ${SLURM_ARRAY_TASK_ID[@]}; do
	echo $i
done
