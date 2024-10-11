#!/bin/bash

write_csv() {
    echo $1, $2, $3, $4, $5, $6, $7 >> result.csv
}

rm result.csv
echo "Id, Total count, T count, S count, CX count, H count, X count" >> result.csv

for i in {1..10000000}
do
    total_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit" -h /tmp/ postgres)
    t_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='ZPowGate**0.25' or type='ZPowGate**-0.25'" -h /tmp/ postgres)
    s_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='ZPowGate**0.5' or type='ZPowGate**-0.5'" -h /tmp/ postgres)
    cx_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='CXPowGate'" -h /tmp/ postgres)
    h_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='HPowGate'" -h /tmp/ postgres)
    x_count=$( /Library/PostgreSQL/14/bin/psql -X -A -t -c "select count(*) from linked_circuit where type='_PauliX'" -h /tmp/ postgres)

    echo $i, $total_count, $t_count, $s_count, $cx_count, $h_count, $x_count
    write_csv $(( i )) $(( total_count )) $(( t_count )) $(( s_count )) $(( cx_count )) $(( h_count )) $(( x_count ))
	sleep 5
done
