#!/bin/bash

FNAME="$1"

echo "clean $FNAME"
rm -f $FNAME
echo "Id, Total count, T count, S count, CX count, H count, X count" >> $FNAME

for i in {1..36}
do
    echo $i

    total_count=$(psql -X -A -t -c "select count(*) from linked_circuit" -U postgres)
    t_count=$(psql -X -A -t -c "select count(*) from linked_circuit where type='ZPowGate**0.25' or type='ZPowGate**-0.25'" -U postgres)
    s_count=$(psql -X -A -t -c "select count(*) from linked_circuit where type='ZPowGate**0.5' or type='ZPowGate**-0.5'" -U postgres)
    cx_count=$(psql -X -A -t -c "select count(*) from linked_circuit where type='CXPowGate'" -U postgres)
    h_count=$(psql -X -A -t -c "select count(*) from linked_circuit where type='HPowGate'" -U postgres)
    x_count=$(psql -X -A -t -c "select count(*) from linked_circuit where type='_PauliX'" -U postgres)

    echo $(( i )) $(( total_count )) $(( t_count )) $(( s_count )) $(( cx_count )) $(( h_count )) $(( x_count )) >> $FNAME
	sleep 5
done

