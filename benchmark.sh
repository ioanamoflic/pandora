#!/bin/bash

FH_SIZE=(10 20 30 40 50)
NPROC=(1 2 4 8 16 32 64)

for p1 in "${FH_SIZE[@]}"; do
    for p2 in "${NPROC[@]}"; do
        filename="fh_${p1}_${p2}_mem.out"
        logfile="fh_${p1}_${p2}_log.out"
        echo "Currently running: main.py $p1 $p2"
        (
            bash mem.sh >> "$filename" &

#            bash run_apptainer.sh main.py default_config.json fh "$p1" "$p2" >> "$logfile"
            python3.10 main.py fh "$p1" "$p2" >> "$logfile"
            pkill -f mem.sh
        )
    done
done
