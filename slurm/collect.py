#!/bin/bash

FNAME="collected_result.csv"
write_csv() {
    echo $1, $2, $3, $4, $5, $6, $7 >> $FNAME
}

rm $FNAME
#echo "Id, Total count, T count, S count, CX count, H count, X count" >> $FNAME

#SQL="`select count(*) from linked_circuit`"

for i in {1..100}
do
	echo " --- RUN $i"
	for nhost in `cat machinefile.txt`
	do
		echo $nhost

#		total_count=$(apptainer exec pandora.sif psql -h $nhost -U $USER -p 5432 -d postgres -X -A -t -c "select count(*) from linked_circuit where type='ZPowGate**0.25' or type='ZPowGate**-0.25'")
		total_count=$(apptainer exec pandora.sif psql -h $nhost -U $USER -p 5432 -d postgres -X -A -t -c "select count(*) from linked_circuit")

		echo $nhost, $i, $total_count
		echo $nhost, $i, $total_count >> $FNAME
	done
	sleep 2
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
