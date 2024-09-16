create or replace procedure linked_toffoli_decomp()
    language plpgsql
as
$$
declare
    toffoli record;

    -- Toffoli neighbours
    tof_prev_q1_id bigint;
	tof_prev_q2_id bigint;
	tof_next_q1_id bigint;
	tof_next_q2_id bigint;
    tof_prev_q3_id bigint;
	tof_next_q3_id bigint;

    -- neighbours modulus
    conc_modulus_left_q1 varchar(8);
    conc_modulus_left_q2 varchar(8);
    conc_modulus_left_q3 varchar(8);
    conc_modulus_right_q1 varchar(8);
    conc_modulus_right_q2 varchar(8);
    conc_modulus_right_q3 varchar(8);

    -- synthesis gates
	a_id bigint;
	b_id bigint;
	c_id bigint;
	d_id bigint;
	e_id bigint;
    f_id bigint;
	g_id bigint;
	h_id bigint;
	i_id bigint;
	j_id bigint;
    k_id bigint;
	l_id bigint;
	m_id bigint;
	n_id bigint;
	o_id bigint;

    -- utility variables
	found boolean = true;
	count int = 0;
    distinct_count int;
    distinct_existing int;
	start_time timestamptz = clock_timestamp();
begin
	while found = true loop
		count := count + 1;
		found := false;

    	select * into toffoli from linked_circuit_qubit as it where it.type = 'CCXPowGate' for update skip locked limit 1;

    	if toffoli.id is not null then
    	    tof_prev_q1_id := div(toffoli.prev_q1, 10);
			tof_prev_q2_id := div(toffoli.prev_q2, 10);
			tof_prev_q3_id := div(toffoli.prev_q3, 10);
			tof_next_q1_id := div(toffoli.next_q1, 10);
			tof_next_q2_id := div(toffoli.next_q2, 10);
			tof_next_q3_id := div(toffoli.next_q3, 10);

    	    conc_modulus_left_q1 := 'next_q' || mod(toffoli.prev_q1, 10) + 1;
			conc_modulus_left_q2 := 'next_q' || mod(toffoli.prev_q2, 10) + 1;
    	    conc_modulus_left_q3 := 'next_q' || mod(toffoli.prev_q3, 10) + 1;
			conc_modulus_right_q1 := 'prev_q' || mod(toffoli.next_q1, 10) + 1;
			conc_modulus_right_q2 := 'prev_q' || mod(toffoli.next_q2, 10) + 1;
			conc_modulus_right_q3 := 'prev_q' || mod(toffoli.next_q3, 10) + 1;

    	    select count(*) into distinct_count from (select distinct unnest(array[tof_prev_q1_id, tof_prev_q2_id, tof_prev_q3_id, tof_next_q1_id, tof_next_q2_id, tof_next_q3_id])) as it;
			select count(*) into distinct_existing from
			        (select * from linked_circuit_qubit where id in (tof_prev_q1_id, tof_prev_q2_id, tof_prev_q3_id, tof_next_q1_id, tof_next_q2_id, tof_next_q3_id) for update skip locked) as it;

			if distinct_count = distinct_existing then
                insert into linked_circuit_qubit values (default, toffoli.prev_q3, null, null, 'HPowGate', 1, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_3, null, null)
                                                      returning id into a_id;
                insert into linked_circuit_qubit values (default, toffoli.prev_q2, a_id * 10, null, 'CXPowGate', 1, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_2, toffoli.qub_3, null)
                                                      returning id into b_id;
                insert into linked_circuit_qubit values (default, b_id * 10 + 1, null, null, 'ZPowGate**-0.25', -0.25, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_3, null, null)
                                                      returning id into c_id;
                insert into linked_circuit_qubit values (default, toffoli.prev_q1, c_id * 10, null, 'CXPowGate', 1, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_1, toffoli.qub_3, null)
                                                      returning id into d_id;
                insert into linked_circuit_qubit values (default, d_id * 10 + 1, null, null, 'ZPowGate**0.25', 0.25, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_3, null, null)
                                                      returning id into e_id;
                insert into linked_circuit_qubit values (default, b_id * 10, e_id * 10, null, 'CXPowGate', 1, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_2, toffoli.qub_3, null)
                                                      returning id into f_id;
                insert into linked_circuit_qubit values (default, f_id * 10 + 1, null, null, 'ZPowGate**-0.25', -0.25, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_3, null, null)
                                                      returning id into g_id;
                insert into linked_circuit_qubit values (default, d_id * 10, g_id * 10, null, 'CXPowGate', 1, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_1, toffoli.qub_3, null)
                                                      returning id into h_id;
                insert into linked_circuit_qubit values (default, h_id * 10, f_id * 10, null, 'CXPowGate', 1, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_1, toffoli.qub_2, null)
                                                      returning id into i_id;
                insert into linked_circuit_qubit values (default, i_id * 10 + 1, null, null, 'ZPowGate**-0.25', -0.25, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_2, null, null)
                                                      returning id into j_id;
                insert into linked_circuit_qubit values (default, i_id * 10, j_id * 10, null, 'CXPowGate', 1, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_1, toffoli.qub_2, null)
                                                      returning id into k_id;
                insert into linked_circuit_qubit values (default, k_id * 10 , null, null, 'ZPowGate**0.25', 0.25, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_1, null, null)
                                                      returning id into l_id;
                insert into linked_circuit_qubit values (default, k_id * 10 + 1, null, null, 'ZPowGate**0.25', 0.25, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_2, null, null)
                                                      returning id into m_id;
                insert into linked_circuit_qubit values (default, h_id * 10 + 1, null, null, 'ZPowGate**0.25', 0.25, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_3, null, null)
                                                      returning id into n_id;
                insert into linked_circuit_qubit values (default, n_id * 10, null, null, 'HPowGate', 1, false, null, null, null, false, toffoli.label, false, null, toffoli.qub_3, null, null)
                                                      returning id into o_id;

                -- updating remaining next links
                update linked_circuit_qubit set next_q1 = b_id * 10 + 1 where id = a_id;
                update linked_circuit_qubit set (next_q1, next_q2) = (f_id * 10, c_id * 10) where id = b_id;
                update linked_circuit_qubit set next_q1 = d_id * 10 + 1 where id = c_id;
                update linked_circuit_qubit set (next_q1, next_q2) = (h_id * 10, e_id * 10) where id = d_id;
                update linked_circuit_qubit set next_q1 = f_id * 10 where id = e_id;
                update linked_circuit_qubit set (next_q1, next_q2) = (i_id * 10 + 1, g_id * 10) where id = f_id;
                update linked_circuit_qubit set next_q1 = h_id * 10 + 1 where id = g_id;
                update linked_circuit_qubit set (next_q1, next_q2) = (i_id * 10, n_id * 10) where id = h_id;
                update linked_circuit_qubit set (next_q1, next_q2) = (k_id * 10, j_id * 10) where id = i_id;
                update linked_circuit_qubit set next_q1 = k_id * 10 + 1 where id = j_id;
                update linked_circuit_qubit set (next_q1, next_q2) = (l_id * 10, m_id * 10) where id = k_id;
                update linked_circuit_qubit set next_q1 = toffoli.next_q1 where id = l_id;
                update linked_circuit_qubit set next_q1 = toffoli.next_q2 where id = m_id;
                update linked_circuit_qubit set next_q1 = o_id * 10 where id = n_id;
                update linked_circuit_qubit set next_q1 = toffoli.next_q3 where id = o_id;

                execute 'update linked_circuit_qubit set ' || conc_modulus_left_q1 || ' = $1 where id = $2' using d_id * 10, tof_prev_q1_id;
                execute 'update linked_circuit_qubit set ' || conc_modulus_left_q2 || ' = $1 where id = $2' using b_id * 10, tof_prev_q2_id;
                execute 'update linked_circuit_qubit set ' || conc_modulus_left_q3 || ' = $1 where id = $2' using a_id * 10, tof_prev_q3_id;
                execute 'update linked_circuit_qubit set ' || conc_modulus_right_q1 || ' = $1 where id = $2' using l_id * 10, tof_next_q1_id;
                execute 'update linked_circuit_qubit set ' || conc_modulus_right_q2 || ' = $1 where id = $2' using m_id * 10, tof_next_q2_id;
                execute 'update linked_circuit_qubit set ' || conc_modulus_right_q3 || ' = $1 where id = $2' using o_id * 10, tof_next_q3_id;

                delete from linked_circuit_qubit where id=toffoli.id;
            end if;
			found := true;
            commit;
		end if;
	    if mod(count, 1000) = 0 then
            raise notice '% %', count, clock_timestamp() - start_time;
        end if;
	end loop;
	raise notice 'Time spent decomposing all Toffoli  gates = %', clock_timestamp() - start_time;
end;$$;

-- alter procedure linked_toffoli_decomp() owner to postgres;

