create or replace procedure commute_single_control_left(single_type varchar(25), sys_range int, run_nr int)
   language plpgsql
as
$$
declare
    cx record;
    sg record;
    distinct_count int;
    distinct_existing int;
    cx_next_q1 bigint;
    cx_next_id bigint;
    cx_prev_id bigint;
    cx_prev_q1 bigint;
    sg_prev_id bigint;
    modulus_prev varchar(8);
    modulus_next varchar(8);
    stop boolean;
begin
	while run_nr > 0 loop
	    select st.stop into stop from stop_condition as st limit 1;
            if stop=True then
                exit;
        end if;
    	select * into cx from (select * from linked_circuit_qubit lc tablesample system_rows(sys_range)) as it where it.type='CXPowGate' for update skip locked limit 1;

    	if cx.id is not null then
    	    cx_next_q1 = cx.next_q1;
    	    cx_prev_q1 = cx.prev_q1;
    	    cx_prev_id = div(cx.prev_q1, 10);
    	    cx_next_id := div(cx.next_q1, 10);
            select * into sg from linked_circuit_qubit where id = cx_prev_id for update skip locked;

    	    if sg.id is not null and sg.type = single_type then
    	        sg_prev_id := div(sg.prev_q1, 10);

    	        select count(*) into distinct_count from (select distinct unnest(array[sg_prev_id, cx_next_id])) as it;
			    select count(*) into distinct_existing from (select * from linked_circuit_qubit where id in (sg_prev_id, cx_next_id) for update skip locked) as it;

    	        if distinct_count = distinct_existing then
    	            modulus_prev := 'next_q' || mod(sg.prev_q1, 10) + 1;
			        modulus_next := 'prev_q' || mod(cx.next_q1, 10) + 1;

                    execute 'update linked_circuit_qubit set ' || modulus_prev || ' = $1 where id = $2' using cx.id * 10, sg_prev_id;
			        execute 'update linked_circuit_qubit set ' || modulus_next || ' = $1 where id = $2' using sg.id * 10, cx_next_id;

                    update linked_circuit_qubit set (next_q1, prev_q1, visited) = (sg.id * 10, sg.prev_q1, false) where id = cx.id;
                    update linked_circuit_qubit set (next_q1, prev_q1) = (cx_next_q1, cx.id * 10) where id = sg.id;
                end if;
    	        run_nr = run_nr - 1;
			end if;
    	    commit;
		end if;
	end loop;
end;$$;
