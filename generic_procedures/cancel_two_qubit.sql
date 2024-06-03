create or replace procedure cancel_two_qubit(type_1 varchar(8), type_2 varchar(8), sys_range int, run_nr int)
    language plpgsql
as
$$
declare
	modulus_first_prev_q1 varchar(8);
	modulus_first_prev_q2 varchar(8);
	modulus_second_next_q1 varchar(8);
	modulus_second_next_q2 varchar(8);
    first_id_plus_one int;
    first_id_plus_zero int;
	first_prev_q1 int;
	first_prev_q2 int;
    second_next_q1 int;
	second_next_q2 int;
    distinct_count int;
    distinct_existing int;
    first record;
    second record;
    stop boolean;
begin
	while run_nr > 0 loop
	    select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;
    	select * into first from (select * from linked_circuit lc tablesample bernoulli(sys_range)) as it where it.type=type_1 for update skip locked limit 1;
    	if first.id is not null then
    	    first_id_plus_one := first.id * 10 + 1;
            first_id_plus_zero := first.id * 10;
            select * into second from linked_circuit where prev_q1 = first_id_plus_zero and prev_q2 = first_id_plus_one and switch = first.switch for update skip locked;

			if second.id is not null and second.type=type_2 then
			    first_prev_q1 := div(first.prev_q1, 10);
			    first_prev_q2 := div(first.prev_q2, 10);
			    second_next_q1 := div(second.next_q1, 10);
			    second_next_q2 := div(second.next_q2, 10);

                select count(*) into distinct_count from (select distinct unnest(array[first_prev_q1, first_prev_q2, second_next_q1, second_next_q2])) as it;
			    select count(*) into distinct_existing from
			    (select * from linked_circuit where id in (first_prev_q1, first_prev_q2, second_next_q1, second_next_q2) for update skip locked) as it;

			    if distinct_count = distinct_existing then
			        modulus_first_prev_q1 := 'next_q' || mod(first.prev_q1, 10) + 1;
			        modulus_first_prev_q2 := 'next_q' || mod(first.prev_q2, 10) + 1;
			        modulus_second_next_q1 := 'prev_q' || mod(second.next_q1, 10) + 1;
			        modulus_second_next_q2 := 'prev_q' || mod(second.next_q2, 10) + 1;

			        execute 'update linked_circuit set ' || modulus_first_prev_q1 || ' = $1 where id = $2' using second.next_q1, first_prev_q1;
			        execute 'update linked_circuit set ' || modulus_first_prev_q2 || ' = $1 where id = $2' using second.next_q2, first_prev_q2;
			        execute 'update linked_circuit set ' || modulus_second_next_q1 || ' = $1 where id = $2' using first.prev_q1, second_next_q1;
			        execute 'update linked_circuit set ' || modulus_second_next_q2 || ' = $1 where id = $2' using first.prev_q2, second_next_q2;

                    delete from linked_circuit lc where lc.id in (first.id, second.id);
			        run_nr = run_nr - 1;
                end if;
			else
			    -- swap the order of the gates
                first_id_plus_one := first.id * 10 + 1;
                first_id_plus_zero := first.id * 10;
                select * into second from linked_circuit where id = first.id;
			    select * into first from linked_circuit where next_q1 = first_id_plus_zero and next_q2 = first_id_plus_one and switch = first.switch for update skip locked;

                if first.id is not null and first.type=type_2 then
                    first_prev_q1 := div(first.prev_q1, 10);
                    first_prev_q2 := div(first.prev_q2, 10);
                    second_next_q1 := div(second.next_q1, 10);
                    second_next_q2 := div(second.next_q2, 10);

                    select count(*) into distinct_count from (select distinct unnest(array[first_prev_q1, first_prev_q2, second_next_q1, second_next_q2])) as it;
                    select count(*) into distinct_existing from
                    (select * from linked_circuit where id in (first_prev_q1, first_prev_q2, second_next_q1, second_next_q2) for update skip locked) as it;

                    if distinct_count = distinct_existing then
                        modulus_first_prev_q1 := 'next_q' || mod(first.prev_q1, 10) + 1;
                        modulus_first_prev_q2 := 'next_q' || mod(first.prev_q2, 10) + 1;
                        modulus_second_next_q1 := 'prev_q' || mod(second.next_q1, 10) + 1;
                        modulus_second_next_q2 := 'prev_q' || mod(second.next_q2, 10) + 1;

                        execute 'update linked_circuit set ' || modulus_first_prev_q1 || ' = $1 where id = $2' using second.next_q1, first_prev_q1;
                        execute 'update linked_circuit set ' || modulus_first_prev_q2 || ' = $1 where id = $2' using second.next_q2, first_prev_q2;
                        execute 'update linked_circuit set ' || modulus_second_next_q1 || ' = $1 where id = $2' using first.prev_q1, second_next_q1;
                        execute 'update linked_circuit set ' || modulus_second_next_q2 || ' = $1 where id = $2' using first.prev_q2, second_next_q2;

                        delete from linked_circuit lc where lc.id in (first.id, second.id);
                        run_nr = run_nr - 1;
                    end if;
			    end if;
            end if;
    	    commit;
		end if;
	end loop;
end;$$;
