if [[ $1 == *json ]] 
then
    PYTHONPORT="import json;file=open('$1', 'r');print(json.load(file)['port'])"
    PYTHON_USER="import json;file=open('$1', 'r');print(json.load(file)['user'])"
    PYTHON_DB_NAME="import json;file=open('$1', 'r');print(json.load(file)['database'])"
    PORT=$(echo $PYTHONPORT | python3)
    USER=$(echo $PYTHON_USER | python3)
    DB_NAME=$(echo $PYTHON_DB_NAME | python3)
fi

for d in /scratch/project_462000921/db_data/*/ ; do
    echo "Reading data from $d"

    PGDATA="$d/pgdata+"
    PGRUN="$d/pgrun"

    SCRIPTTORUN="
    echo 'host all all 0.0.0.0/0 trust' >> \"$PGDATA/pg_hba.conf\"

    pg_ctl -D $PGDATA -o \"-p $PORT\" start 

    psql -U $USER -d $DB_NAME \"-p $PORT\" -f /pandora/collect.sql;

    pg_ctl -D $PGDATA -o \"-p $PORT\" stop
    "
    export EXEC="srun singularity exec -B $d -B $PGDATA:/var/lib/postgresql/data -B $PGRUN:/var/run/postgresql -B $(pwd):/pandora -e -C apptainer/images/pandora_new.sif"

    $EXEC bash -c "$SCRIPTTORUN"
done

# psql -U $USER -d $DB_NAME \"-p $PORT\" -c \"drop table if exists edge_list, layered_cliff_t, stop_condition, benchmark_results, linked_circuit_test, batched_circuit, linked_circuit\";
