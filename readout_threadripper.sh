#!/bin/bash

write_csv() {
    echo $1,$2,$3,$4,$5,$6,$7 >> result.csv
}

echo "Id,Total count,T count,S count,CX count,H count,X count" >> result.csv

for i in {1..10000000}
do
    total_count=$( /usr/lib/postgresql/14/bin/psql -X -A -t -c "select count(*) from linked_circuit" -U postgres)
    t_count=$( /usr/lib/postgresql/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='ZPowGate**0.25' or type='ZPowGate**-0.25'" -U postgres)
    s_count=$( /usr/lib/postgresql/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='ZPowGate**0.5' or type='ZPowGate**-0.5'" -U postgres)
    cx_count=$( /usr/lib/postgresql/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='CXPowGate'" -U postgres)
    h_count=$( /usr/lib/postgresql/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='HPowGate'" -U postgres)
    x_count=$( /usr/lib/postgresql/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='_PauliX'" -U postgres)
    echo $i, $total_count, $t_count, $s_count, $cx_count, $h_count, $x_count
    write_csv $(( i )) $(( total_count )) $(( t_count )) $(( s_count )) $(( cx_count )) $(( h_count )) $(( x_count ))
	sleep 5
done
