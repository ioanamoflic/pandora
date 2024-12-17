create or replace procedure commute_cx_ctrl_target_bernoulli(sys_range integer, run_nr integer)
    language plpgsql
as
$$
declare
    first_cx record;
    second_cx record;

    distinct_count int;
    distinct_existing int;

    first_prev_q2_id bigint;
    first_next_q1_id bigint;
    second_prev_q1_id bigint;
    second_next_q2_id bigint;
    first_next_q2_id bigint;
    third_cx_id bigint;
    second_next_q1_id bigint;

    modulus_first_next_q1 varchar(10);
    modulus_first_next_q2 varchar(10);
    modulus_second_prev_q1 varchar(10);
    modulus_second_next_q2 varchar(10);
    modulus_first_prev_q2 varchar(10);
    modulus_second_next_q1 varchar(10);

    mod_first_prev_q2 int;
    mod_first_next_q2 int;

    stop boolean;
begin
	while run_nr > 0 loop
	    select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;

    	select * into first_cx from (select * from linked_circuit lc tablesample bernoulli(sys_range)) as it
    	                       where it.type in (15, 18) for update skip locked limit 1;
    	if first_cx.id is not null then
    	    first_prev_q2_id = div(first_cx.prev_q2, 10);
    	    mod_first_prev_q2 = mod(first_cx.prev_q2, 10);

    	    first_next_q1_id = div(first_cx.next_q1, 10);
    	    first_next_q2_id = div(first_cx.next_q2, 10);
    	    mod_first_next_q2 = mod(first_cx.next_q2, 10);

    	    -- upper CNOT might be the second CNOT
            if mod_first_prev_q2 = 0 then
                select * into second_cx from linked_circuit where id = first_prev_q2_id for update skip locked;

                if second_cx.id is not null and second_cx.type in (15, 18) then
                    second_prev_q1_id = div(second_cx.prev_q1, 10);
    	            second_next_q2_id = div(second_cx.next_q2, 10);

                    select count(*) into distinct_count from (select distinct unnest(array[first_cx.id, second_cx.id, first_next_q1_id, first_next_q2_id, second_prev_q1_id, second_next_q2_id])) as it;
                    select count(*) into distinct_existing from (select * from linked_circuit where id in (first_cx.id, second_cx.id, first_next_q1_id, first_next_q2_id, second_prev_q1_id, second_next_q2_id) for update skip locked) as it;

                    if distinct_count = distinct_existing then
                        modulus_first_next_q1 := 'prev_q' || mod(first_cx.next_q1, 10) + 1;
                        modulus_first_next_q2 := 'prev_q' || mod(first_cx.next_q2, 10) + 1;

                        modulus_second_prev_q1 := 'next_q' || mod(second_cx.prev_q1, 10) + 1;
                        modulus_second_next_q2 := 'prev_q' || mod(second_cx.next_q2, 10) + 1;

                        insert into linked_circuit values (default, first_cx.id * 10, second_cx.id * 10 + 1, null, 15, 1, 0, false, first_cx.next_q1, second_cx.next_q2, null, false, first_cx.label, false, null)
                                                      returning id into third_cx_id;

                        execute 'update linked_circuit set ' || modulus_first_next_q1 || ' = $1 where id = $2' using third_cx_id * 10, first_next_q1_id;
                        execute 'update linked_circuit set ' || modulus_first_next_q2 || ' = $1 where id = $2' using second_cx.id * 10, first_next_q2_id;

                        execute 'update linked_circuit set ' || modulus_second_prev_q1 || ' = $1 where id = $2' using first_cx.id * 10 + 1, second_prev_q1_id;
                        execute 'update linked_circuit set ' || modulus_second_next_q2 || ' = $1 where id = $2' using third_cx_id * 10 + 1, second_next_q2_id;

                        update linked_circuit set (next_q1, next_q2, prev_q2) = (third_cx_id * 10, second_cx.id * 10, second_cx.prev_q1) where id = first_cx.id;
                        update linked_circuit set (next_q1, prev_q1, next_q2) = (first_next_q2_id * 10 + mod_first_next_q2, first_cx.id * 10, third_cx_id * 10 + 1) where id = second_cx.id;
                    end if;
                    run_nr = run_nr - 1;
                else
                    if mod_first_next_q2 = 0 then
                      select * into second_cx from linked_circuit where id = first_next_q2_id for update skip locked;
                        if second_cx.id is not null and second_cx.type in (15, 18) then

                            second_prev_q1_id = div(second_cx.prev_q1, 10);
                            second_next_q1_id = div(second_cx.next_q1, 10);
                            second_next_q2_id = div(second_cx.next_q2, 10);

                            select count(*) into distinct_count from (select distinct unnest(array[first_cx.id, second_cx.id, first_prev_q2_id, first_next_q1_id, second_next_q2_id, second_next_q2_id])) as it;
                            select count(*) into distinct_existing from (select * from linked_circuit where id in (first_cx.id, second_cx.id, first_prev_q2_id, first_next_q1_id, second_next_q2_id, second_next_q2_id) for update skip locked) as it;

                            if distinct_count = distinct_existing then
                                modulus_first_next_q1 := 'prev_q' || mod(first_cx.next_q1, 10) + 1;
                                modulus_first_prev_q2 := 'next_q' || mod(first_cx.prev_q2, 10) + 1;

                                modulus_second_next_q1 := 'prev_q' || mod(second_cx.next_q1, 10) + 1;
                                modulus_second_next_q2 := 'prev_q' || mod(second_cx.next_q2, 10) + 1;

                                insert into linked_circuit values (default, first_cx.id * 10, second_cx.id * 10 + 1, null, 15, 1, 0, false, first_cx.next_q1, second_cx.next_q2, null, false, first_cx.label, false, null)
                                                              returning id into third_cx_id;

                                execute 'update linked_circuit set ' || modulus_first_next_q1 || ' = $1 where id = $2' using third_cx_id * 10, first_next_q1_id;
                                execute 'update linked_circuit set ' || modulus_first_prev_q2 || ' = $1 where id = $2' using second_cx.id * 10, first_prev_q2_id;

                                execute 'update linked_circuit set ' || modulus_second_next_q1 || ' = $1 where id = $2' using first_cx.id * 10 + 1, second_next_q1_id;
                                execute 'update linked_circuit set ' || modulus_second_next_q2 || ' = $1 where id = $2' using third_cx_id * 10 + 1, second_next_q2_id;

                                update linked_circuit set (next_q1, next_q2, prev_q2) = (third_cx_id * 10, second_cx.next_q1, second_cx.id * 10) where id = first_cx.id;
                                update linked_circuit set (next_q1, prev_q1, next_q2) = (first_cx.id * 10 + 1, first_prev_q2_id * 10 + mod_first_prev_q2, third_cx_id * 10 + 1) where id = second_cx.id;
                            end if;
                            run_nr = run_nr - 1;
                        end if;
                    end if;
                end if;
                commit;
            end if;
    	end if;
	end loop;
end;$$;
