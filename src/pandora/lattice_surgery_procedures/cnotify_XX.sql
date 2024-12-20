create or replace procedure cnotify_XX(sys_range int, run_nr int)
    language plpgsql
as
$$
declare
    xx_next_id_q1 bigint;
    xx_next_id_q2 bigint;
    xx_prev_id_q1 bigint;
    xx_prev_id_q2 bigint;

    plus_id bigint;
	xc_id bigint;
	cx_id bigint;
	m_out_id bigint;

    conc_mod_left_q1 varchar(10);
    conc_mod_left_q2 varchar(10);
    conc_mod_right_q1 varchar(10);
    conc_mod_right_q2 varchar(10);

    xx record;
    distinct_count bigint;
    distinct_existing bigint;
    stop boolean;
begin
	while run_nr > 0 loop
	    select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;
    	select * into xx from (select * from linked_circuit lc tablesample system_rows(sys_range)) as it where it.type='XXPowGate' for update skip locked limit 1;

    	if xx.id is not null then
    	    xx_next_id_q1 :=  div(xx.next_q1, 10);
    	    xx_next_id_q2 :=  div(xx.next_q2, 10);
    	    xx_prev_id_q1 :=  div(xx.prev_q1, 10);
    	    xx_prev_id_q2 :=  div(xx.prev_q2, 10);

    	    conc_mod_left_q1 := 'next_q' || mod(xx.prev_q1, 10) + 1;
			conc_mod_left_q2 := 'next_q' || mod(xx.prev_q2, 10) + 1;
			conc_mod_right_q1 := 'prev_q' || mod(xx.next_q1, 10) + 1;
			conc_mod_right_q2 := 'prev_q' || mod(xx.next_q2, 10) + 1;

			select count(*) into distinct_count from (select distinct unnest(array[xx_next_id_q1, xx_next_id_q2, xx_prev_id_q1, xx_prev_id_q2])) as it;
		    select count(*) into distinct_existing from (select id from linked_circuit where id in (xx_next_id_q1, xx_next_id_q2, xx_prev_id_q1, xx_prev_id_q2)
			                                                                               for update skip locked) as it;
			if distinct_count = distinct_existing then
			    insert into linked_circuit values (default, null, null, null, 'In', 1, false, null, null, null, false, xx.label, false, '|+>')
                                                      returning id into plus_id;
                insert into linked_circuit values (default, plus_id * 10, xx.prev_q1, null, 'CXPowGate', 1, false, null, xx.next_q1, null, false, xx.label, false, null)
                                                      returning id into xc_id;
                insert into linked_circuit values (default, xc_id * 10, xx.prev_q2, null, 'CXPowGate', 1, false, null, xx.next_q2, null, false, xx.label, false, null)
                                                      returning id into cx_id;
                insert into linked_circuit values (default, cx_id * 10, null, null, 'Out', 1, false, null, null, null, false, xx.label, false, 'Mx')
                                                      returning id into m_out_id;

			    update linked_circuit set next_q1 = xc_id * 10 where id = plus_id;
			    update linked_circuit set next_q1 = cx_id * 10 where id = xc_id;
			    update linked_circuit set next_q1 = m_out_id * 10 where id = cx_id;

                execute 'update linked_circuit set ' || conc_mod_left_q1 || ' = $1 where id = $2' using xc_id * 10 + 1, xx_prev_id_q1;
                execute 'update linked_circuit set ' || conc_mod_left_q2 || ' = $1 where id = $2' using cx_id * 10 + 1, xx_prev_id_q2;
                execute 'update linked_circuit set ' || conc_mod_right_q1 || ' = $1 where id = $2' using xc_id * 10 + 1, xx_next_id_q1;
                execute 'update linked_circuit set ' || conc_mod_right_q2 || ' = $1 where id = $2' using cx_id * 10 + 1, xx_next_id_q2;

			    delete from linked_circuit where id=xx.id;
			    run_nr = run_nr - 1;
			end if;
    	    commit;
		end if;
	end loop;
end;$$;
