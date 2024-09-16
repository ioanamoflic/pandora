-- this procedure needs more testing done before usage
create or replace procedure insert_two_qubit(type_1 varchar(25), type_2 varchar(25), sys_range int)
    language plpgsql
as
$$
declare
	modulus_second_next_q1 varchar(8);
	modulus_second_next_q2 varchar(8);
    first_next_q1_id bigint;
	first_next_q2_id bigint;
    distinct_count int;
    distinct_existing int;
    first_insert_id bigint;
    second_insert_id bigint;
    first record;
    stop boolean;
begin
	while true loop
	    select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;
    	select * into first from (select * from linked_circuit_qubit lc tablesample system_rows(sys_range)) as it where it.type=type_1 for update skip locked limit 1;
    	if first.id is not null then
			first_next_q1_id := div(first.next_q1, 10);
			first_next_q2_id := div(first.next_q2, 10);

            select count(*) into distinct_count from (select distinct unnest(array[first_next_q1_id, first_next_q2_id])) as it;
			select count(*) into distinct_existing from
			(select * from linked_circuit_qubit where id in (first_next_q1_id, first_next_q2_id) for update skip locked) as it;

			if distinct_count = distinct_existing then
			    modulus_second_next_q1 := 'prev_q' || mod(first.next_q1, 10) + 1;
			    modulus_second_next_q2 := 'prev_q' || mod(first.next_q2, 10) + 1;

			    insert into linked_circuit_qubit values (DEFAULT, first.id * 10 + 1, first.id * 10, null, type_2, 0, not first.switch, null, null, null, false, first.label, first.qub_1, null, null)
                                                              returning id into first_insert_id;
                insert into linked_circuit_qubit values (DEFAULT, first_insert_id * 10, first_insert_id * 10 + 1, null, type_2, 0, not first.switch, first.next_q2, first.next_q1, null, false, first.label, first.qub_1, null, null)
                                                              returning id into second_insert_id;

                update linked_circuit_qubit set (next_q1, next_q2) = (second_insert_id * 10, second_insert_id * 10 + 1) where id = first_insert_id;
                update linked_circuit_qubit set (next_q1, next_q2) = (first_insert_id * 10 + 1, first_insert_id * 10) where id = first.id;

			    execute 'update linked_circuit_qubit set ' || modulus_second_next_q1 || ' = $1 where id = $2' using second_insert_id * 10 + 1, first_next_q1_id;
			    execute 'update linked_circuit_qubit set ' || modulus_second_next_q2 || ' = $1 where id = $2' using second_insert_id * 10, first_next_q2_id;
            end if;
			commit;
		end if;
	end loop;
end;$$;
