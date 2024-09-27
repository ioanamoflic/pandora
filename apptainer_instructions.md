# https://gitlab.oit.duke.edu/OIT-DCC/postgres

# https://docs.csc.fi/data/sensitive-data/tutorials/postgresql/

```
mkdir pgdata
mkdir pgrun
apptainer shell -B pgdata:/var/lib/postgresql/data -B pgrun:/var/run/postgresql -e -C  pandora.sif
```

in the running container

```
pg_ctl init
pg_ctl start

export PYTHONPATH="$PYTHONPATH:/pandora"
cd /pandora
python3.10 benchmarking/benchmark_db.py
```
