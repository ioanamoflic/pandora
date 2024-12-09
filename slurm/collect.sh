#!/bin/bash

echo "-----------------------collector side--------------------------"
echo "The collector running on $(hostname) "
echo "This job started at $(date +%Y-%m-%dT%T)"
echo "This job will end at $(squeue --noheader -j $SLURM_JOBID -o %e) (in $(squeue --noheader -j $SLURM_JOBID -o %L))"
echo "---------------------++++collector side++++--------------------------"


FNAME="collected_result.csv"
write_csv() {
    echo $1, $2, $3, $4, $5, $6, $7 >> $FNAME
}

rm $FNAME

#echo "Id, Total count, T count, S count, CX count, H count, X count" >> $FNAME
#SQL="`select count(*) from linked_circuit`"
#/usr/lib/postgresql/14/bin/pg_isready -h $nhost -U redouane.bouchouirba -p 5432

# https://stackoverflow.com/questions/2953646/how-can-i-declare-and-use-boolean-variables-in-a-shell-script

DBUSER=redouane.bouchourba
startcollect=true

# We wait for all the hosts to be running the database
while [ "$startcollect" = true ]
do
    startcollect=true
    for nhost in `cat machinefile.txt`
    do

        # Avoid connecting to the host running the collector
        if [ "$nhost" = $(hostname)]; then
            continue
        fi

        apptainer exec pandora.sif /usr/bin/pg_isready -h $nhost -U $DBUSER -d postgres -p 5432 -t5
        ret=$(apptainer exec pandora.sif echo $?)

        # we check if the connection failed. this means the database is not running
        if [ $ret -ne 0 ]; then
            startcollect=false
        fi
    done
done


# We collect from each Pandora for a specified number of times, e.g. 100
for i in {1..100}
do
    echo " --- RUN $i"
    for nhost in `cat machinefile.txt`
    do
        # We should not connect to the host running the collector
        if [ "$nhost" -ne $(hostname) ]; then
            echo $nhost

            #for example, get the number of gates from the Pandora
            total_count=$(apptainer exec pandora.sif psql -h $nhost -U $DBUSER -p 5432 -d postgres -X -A -t -c "select count(*) from linked_circuit")
            echo $nhost, $i, $total_count
            echo $nhost, $i, $total_count >> $FNAME
        fi
    done
    sleep 1
done


#for i in {1..10000000}
#do
#    total_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit" -h /tmp/ postgres)
#    t_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='ZPowGate**0.25' or type='ZPowGate**-0.25'" -h /tmp/ postgres)
#    s_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='ZPowGate**0.5' or type='ZPowGate**-0.5'" -h /tmp/ postgres)
#    cx_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='CXPowGate'" -h /tmp/ postgres)
#    h_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='HPowGate'" -h /tmp/ postgres)
#    x_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='_PauliX'" -h /tmp/ postgres)

#    echo $i, $total_count, $t_count, $s_count, $cx_count, $h_count, $x_count
#    write_csv $(( i )) $(( total_count )) $(( t_count )) $(( s_count )) $(( cx_count )) $(( h_count )) $(( x_count ))
#	sleep 5
#done
