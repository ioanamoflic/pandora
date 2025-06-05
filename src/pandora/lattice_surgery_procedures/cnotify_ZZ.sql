create or replace procedure cnotify_ZZ(sys_range int, run_nr int)
    language plpgsql
as
$$
declare
    zz_next_id_q1 bigint;
    zz_next_id_q2 bigint;
    zz_prev_id_q1 bigint;
    zz_prev_id_q2 bigint;

    zero_id bigint;
	xc_id bigint;
	cx_id bigint;
	m_out_id bigint;

    conc_mod_left_q1 varchar(10);
    conc_mod_left_q2 varchar(10);
    conc_mod_right_q1 varchar(10);
    conc_mod_right_q2 varchar(10);

    zz record;
    distinct_count bigint;
    distinct_existing bigint;
    stop boolean;
begin
	while run_nr > 0 loop
	    select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;
    	select * into zz from (select * from linked_circuit lc tablesample system_rows(sys_range)) as it where it.type=20 for update skip locked limit 1;

    	if zz.id is not null then
    	    zz_next_id_q1 :=  div(zz.next_q1, 10);
    	    zz_next_id_q2 :=  div(zz.next_q2, 10);
    	    zz_prev_id_q1 :=  div(zz.prev_q1, 10);
    	    zz_prev_id_q2 :=  div(zz.prev_q2, 10);

    	    conc_mod_left_q1 := 'next_q' || mod(zz.prev_q1, 10) + 1;
			conc_mod_left_q2 := 'next_q' || mod(zz.prev_q2, 10) + 1;
			conc_mod_right_q1 := 'prev_q' || mod(zz.next_q1, 10) + 1;
			conc_mod_right_q2 := 'prev_q' || mod(zz.next_q2, 10) + 1;

			select count(*) into distinct_count from (select distinct unnest(array[zz_next_id_q1, zz_next_id_q2, zz_prev_id_q1, zz_prev_id_q2])) as it;
		    select count(*) into distinct_existing from (select id from linked_circuit where id in (zz_next_id_q1, zz_next_id_q2, zz_prev_id_q1, zz_prev_id_q2)
			                                                                               for update skip locked) as it;
			if distinct_count = distinct_existing then
			    insert into linked_circuit values (default, null, null, null, 0, 1, 0, false, null, null, null, false, zz.label, false, 0)
                                                      returning id into zero_id;
                insert into linked_circuit values (default, zz.prev_q1, zero_id * 10, null, 18, 1, 0, false, zz.next_q1, null, null, false, zz.label, false, null)
                                                      returning id into cx_id;
                insert into linked_circuit values (default, zz.prev_q2, cx_id * 10 + 1, null, 18, 1, 0, false, zz.next_q2, null, null, false, zz.label, false, null)
                                                      returning id into xc_id;
                insert into linked_circuit values (default, xc_id * 10 + 1, null, null, 1, 1, 0, false, null, null, null, false, zz.label, false, 1)
                                                      returning id into m_out_id;

			    update linked_circuit set next_q1 = cx_id * 10 + 1 where id = zero_id;
			    update linked_circuit set next_q2 = xc_id * 10 + 1 where id = cx_id;
			    update linked_circuit set next_q2 = m_out_id * 10 where id = xc_id;

                execute 'update linked_circuit set ' || conc_mod_left_q1 || ' = $1 where id = $2' using cx_id * 10, zz_prev_id_q1;
                execute 'update linked_circuit set ' || conc_mod_left_q2 || ' = $1 where id = $2' using xc_id * 10, zz_prev_id_q2;
                execute 'update linked_circuit set ' || conc_mod_right_q1 || ' = $1 where id = $2' using cx_id * 10, zz_next_id_q1;
                execute 'update linked_circuit set ' || conc_mod_right_q2 || ' = $1 where id = $2' using xc_id * 10, zz_next_id_q2;

			    delete from linked_circuit where id=zz.id;
			    run_nr = run_nr - 1;
			end if;
    	    commit;
		end if;
	end loop;
end;$$;
