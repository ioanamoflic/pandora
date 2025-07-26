create or replace procedure cancel_single_qubit_bernoulli(type_1 int, type_2 int, param_1 float, param_2 float, sys_range int, run_nr int)
    language plpgsql
as
$$
declare
    first_next_id bigint;
    first_prev_id bigint;
    second_next_id bigint;
    modulus_prev varchar(8);
    modulus_next varchar(8);
    first record;
    second record;
    distinct_count int;
    distinct_existing int;
    stop boolean;
begin
	while run_nr > 0 loop
	    select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;
    	select * into first from (select * from linked_circuit lc tablesample bernoulli(sys_range)) as it
    	                    where it.type=type_1 and it.param=param_1 for update skip locked limit 1;
    	if first.id is not null then
    	    first_next_id :=  div(first.next_q1, 10);
			select * into second from linked_circuit where id = first_next_id for update skip locked;

			if second.id is not null and second.type=type_2 and second.param=param_2 then
			    first_prev_id := div(first.prev_q1, 10);
			    second_next_id := div(second.next_q1, 10);

			    select count(*) into distinct_count from (select distinct unnest(array[first_prev_id, second_next_id])) as it;
			    select count(*) into distinct_existing from (select id from linked_circuit where id in (first_prev_id, second_next_id)
			                                                                               for update skip locked) as it;
			    if distinct_count = distinct_existing then
			        modulus_prev := 'next_q' || mod(first.prev_q1, 10) + 1;
			        modulus_next := 'prev_q' || mod(second.next_q1, 10) + 1;

                    execute 'update linked_circuit set ' || modulus_prev || ' = $1 where id = $2' using second.next_q1, first_prev_id;
			        execute 'update linked_circuit set ' || modulus_next || ' = $1 where id = $2' using first.prev_q1, second_next_id;

                    delete from linked_circuit lc where lc.id in (first.id, second.id);
			        run_nr = run_nr - 1;
                end if;
			else
			    -- swap the order of the gates
			    first_prev_id :=  div(first.prev_q1, 10);
			    select * into second from linked_circuit where id = first.id;
			    select * into first from linked_circuit where id = first_prev_id for update skip locked;

			    if first.id is not null and first.type=type_2 and first.param=param_2 then
                    first_prev_id := div(first.prev_q1, 10);
                    second_next_id := div(second.next_q1, 10);

                    select count(*) into distinct_count from (select distinct unnest(array[first_prev_id, second_next_id])) as it;
                    select count(*) into distinct_existing from (select id from linked_circuit where id in (first_prev_id, second_next_id)
                                                                                               for update skip locked) as it;
                    if distinct_count = distinct_existing then
                        modulus_prev := 'next_q' || mod(first.prev_q1, 10) + 1;
                        modulus_next := 'prev_q' || mod(second.next_q1, 10) + 1;

                        execute 'update linked_circuit set ' || modulus_prev || ' = $1 where id = $2' using second.next_q1, first_prev_id;
                        execute 'update linked_circuit set ' || modulus_next || ' = $1 where id = $2' using first.prev_q1, second_next_id;

                        delete from linked_circuit lc where lc.id in (first.id, second.id);
                        run_nr = run_nr - 1;
                    end if;
			    end if;
		    end if;
    	commit;
        end if;
	end loop;
end;$$;
