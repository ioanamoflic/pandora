#!/bin/bash 
for i in {1..20000}
do
	psql -U postgres -d dbcopt -c "VACUUM FULL VERBOSE linked_circuit"
	sleep 10
done
