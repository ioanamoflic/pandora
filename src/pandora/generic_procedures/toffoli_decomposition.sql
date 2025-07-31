/*create or replace procedure linked_toffoli_decomp()
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
    conc_modulus_left_q1 varchar(10);
    conc_modulus_left_q2 varchar(10);
    conc_modulus_left_q3 varchar(10);
    conc_modulus_right_q1 varchar(10);
    conc_modulus_right_q2 varchar(10);
    conc_modulus_right_q3 varchar(10);

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
begin
	while found = true loop
		count := count + 1;
		found := false;

    	select * into toffoli from linked_circuit as it
    	                      where it.type = 23 for update skip locked limit 1;

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
			        (select * from linked_circuit where id in (tof_prev_q1_id, tof_prev_q2_id, tof_prev_q3_id, tof_next_q1_id, tof_next_q2_id, tof_next_q3_id) for update skip locked) as it;

			if distinct_count = distinct_existing then
                insert into linked_circuit values (default, toffoli.prev_q3, null, null, 8, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into a_id;
                insert into linked_circuit values (default, toffoli.prev_q2, a_id * 10, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into b_id;
                insert into linked_circuit values (default, b_id * 10 + 1, null, null, 7, -0.25, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into c_id;
                insert into linked_circuit values (default, toffoli.prev_q1, c_id * 10, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into d_id;
                insert into linked_circuit values (default, d_id * 10 + 1, null, null, 7, 0.25, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into e_id;
                insert into linked_circuit values (default, b_id * 10, e_id * 10, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into f_id;
                insert into linked_circuit values (default, f_id * 10 + 1, null, null, 7, -0.25, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into g_id;
                insert into linked_circuit values (default, d_id * 10, g_id * 10, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into h_id;
                insert into linked_circuit values (default, h_id * 10, f_id * 10, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into i_id;
                insert into linked_circuit values (default, i_id * 10 + 1, null, null, 7, -0.25, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into j_id;
                insert into linked_circuit values (default, i_id * 10, j_id * 10, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into k_id;
                insert into linked_circuit values (default, k_id * 10 , null, null, 7, 0.25, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into l_id;
                insert into linked_circuit values (default, k_id * 10 + 1, null, null, 7, 0.25, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into m_id;
                insert into linked_circuit values (default, h_id * 10 + 1, null, null, 7, 0.25, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into n_id;
                insert into linked_circuit values (default, n_id * 10, null, null, 8, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                                      returning id into o_id;

                -- updating remaining next links
                update linked_circuit set next_q1 = b_id * 10 + 1 where id = a_id;
                update linked_circuit set (next_q1, next_q2) = (f_id * 10, c_id * 10) where id = b_id;
                update linked_circuit set next_q1 = d_id * 10 + 1 where id = c_id;
                update linked_circuit set (next_q1, next_q2) = (h_id * 10, e_id * 10) where id = d_id;
                update linked_circuit set next_q1 = f_id * 10 where id = e_id;
                update linked_circuit set (next_q1, next_q2) = (i_id * 10 + 1, g_id * 10) where id = f_id;
                update linked_circuit set next_q1 = h_id * 10 + 1 where id = g_id;
                update linked_circuit set (next_q1, next_q2) = (i_id * 10, n_id * 10) where id = h_id;
                update linked_circuit set (next_q1, next_q2) = (k_id * 10, j_id * 10) where id = i_id;
                update linked_circuit set next_q1 = k_id * 10 + 1 where id = j_id;
                update linked_circuit set (next_q1, next_q2) = (l_id * 10, m_id * 10) where id = k_id;
                update linked_circuit set next_q1 = toffoli.next_q1 where id = l_id;
                update linked_circuit set next_q1 = toffoli.next_q2 where id = m_id;
                update linked_circuit set next_q1 = o_id * 10 where id = n_id;
                update linked_circuit set next_q1 = toffoli.next_q3 where id = o_id;

                execute 'update linked_circuit set ' || conc_modulus_left_q1 || ' = $1 where id = $2' using d_id * 10, tof_prev_q1_id;
                execute 'update linked_circuit set ' || conc_modulus_left_q2 || ' = $1 where id = $2' using b_id * 10, tof_prev_q2_id;
                execute 'update linked_circuit set ' || conc_modulus_left_q3 || ' = $1 where id = $2' using a_id * 10, tof_prev_q3_id;
                execute 'update linked_circuit set ' || conc_modulus_right_q1 || ' = $1 where id = $2' using l_id * 10, tof_next_q1_id;
                execute 'update linked_circuit set ' || conc_modulus_right_q2 || ' = $1 where id = $2' using m_id * 10, tof_next_q2_id;
                execute 'update linked_circuit set ' || conc_modulus_right_q3 || ' = $1 where id = $2' using o_id * 10, tof_next_q3_id;

                delete from linked_circuit where id=toffoli.id;
            end if;
			found := true;
            commit;
		end if;
	end loop;
end;$$;

-- alter procedure linked_toffoli_decomp() owner to postgres;*/

create or replace procedure linked_toffoli_cnot_transform()
    language plpgsql
as
$$
declare
    toffoli record;
    cnot record;
    last_id bigint;

    -- New gates to insert (based on A2 circuit)
    gate1_id bigint;
    gate2_id bigint;
    gate3_id bigint;
    gate4_id bigint;
    gate5_id bigint;
    gate6_id bigint;
    gate7_id bigint;
    gate8_id bigint;
    gate9_id bigint;
    gate10_id bigint;
    gate11_id bigint;
    gate12_id bigint;
    gate13_id bigint;
    gate14_id bigint;

    -- utility variables
    found boolean = true;
    count int = 0;
    start_time timestamptz = clock_timestamp();
begin
    while found = true loop
        count := count + 1;
        found := false;

        -- Find a Toffoli gate (type = 23)
        select * into toffoli from linked_circuit as it
                              where it.type = 23 for update skip locked limit 1;

        if toffoli.id is not null then
            -- Find the next gate to see if it's a CNOT
            -- Check multiple possible connections
            select * into cnot from linked_circuit as it
                               where (it.id = toffoli.next_q1 / 10 or 
                                     it.id = toffoli.next_q2 / 10 or 
                                     it.id = toffoli.next_q3 / 10)
                                 and it.type = 18 for update skip locked limit 1;

            if cnot.id is not null then
                -- We found Toffoli followed by CNOT
                -- Replace with the full A2 sequence
                
                -- Get the next available ID
                select max(id) into last_id from linked_circuit;
                if last_id is null then
                    last_id := 0;
                end if;
                last_id := last_id + 1;

                -- Insert the new sequence of gates (A2 pattern)
                -- Gate 1: CNOT(3,2) - First gate connects to original Toffoli's previous gates
                insert into linked_circuit values (last_id, toffoli.prev_q1, toffoli.prev_q2, toffoli.prev_q3, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate1_id;
                last_id := last_id + 1;

                -- Gate 2: Toffoli(1,2,3) - connects to gate1
                insert into linked_circuit values (last_id, gate1_id * 10, gate1_id * 10 + 1, gate1_id * 10 + 2, 23, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate2_id;
                last_id := last_id + 1;

                -- Gate 3: Toffoli(1,2,4) - connects to gate2
                insert into linked_circuit values (last_id, gate2_id * 10, gate2_id * 10 + 1, gate2_id * 10 + 2, 23, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate3_id;
                last_id := last_id + 1;

                -- Gate 4: CNOT(3,4) - connects to gate3
                insert into linked_circuit values (last_id, gate3_id * 10, gate3_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate4_id;
                last_id := last_id + 1;

                -- Gate 5: CNOT(3,0) - connects to gate4
                insert into linked_circuit values (last_id, gate4_id * 10, gate4_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate5_id;
                last_id := last_id + 1;

                -- Gate 6: CNOT(2,0) - connects to gate5
                insert into linked_circuit values (last_id, gate5_id * 10, gate5_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate6_id;
                last_id := last_id + 1;

                -- Gate 7: Toffoli(2,1,0) - connects to gate6
                insert into linked_circuit values (last_id, gate6_id * 10, gate6_id * 10 + 1, gate6_id * 10 + 2, 23, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate7_id;
                last_id := last_id + 1;

                -- Gate 8: Toffoli(1,4,3) - connects to gate7
                insert into linked_circuit values (last_id, gate7_id * 10, gate7_id * 10 + 1, gate7_id * 10 + 2, 23, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate8_id;
                last_id := last_id + 1;

                -- Gate 9: Toffoli(0,1,2) - connects to gate8
                insert into linked_circuit values (last_id, gate8_id * 10, gate8_id * 10 + 1, gate8_id * 10 + 2, 23, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate9_id;
                last_id := last_id + 1;

                -- Gate 10: CNOT(2,4) - connects to gate9
                insert into linked_circuit values (last_id, gate9_id * 10, gate9_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate10_id;
                last_id := last_id + 1;

                -- Gate 11: Toffoli(0,1,4) - connects to gate10
                insert into linked_circuit values (last_id, gate10_id * 10, gate10_id * 10 + 1, gate10_id * 10 + 2, 23, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate11_id;
                last_id := last_id + 1;

                -- Gate 12: CNOT(0,4) - connects to gate11
                insert into linked_circuit values (last_id, gate11_id * 10, gate11_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate12_id;
                last_id := last_id + 1;

                -- Gate 13: CNOT(2,0) - connects to gate12
                insert into linked_circuit values (last_id, gate12_id * 10, gate12_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate13_id;
                last_id := last_id + 1;

                -- Gate 14: CNOT(3,0) - connects to gate13 and to original CNOT's next gates
                insert into linked_circuit values (last_id, gate13_id * 10, gate13_id * 10 + 1, null, 18, 1, 0, false, cnot.next_q1, cnot.next_q2, cnot.next_q3, false, toffoli.label, false, null)
                                              returning id into gate14_id;

                -- Update connections for the new sequence
                -- Connect the first gate to the original Toffoli's previous gates
                if toffoli.prev_q1 is not null then
                    update linked_circuit set next_q1 = gate1_id * 10 where id = div(toffoli.prev_q1, 10);
                end if;
                if toffoli.prev_q2 is not null then
                    update linked_circuit set next_q2 = gate1_id * 10 + 1 where id = div(toffoli.prev_q2, 10);
                end if;
                if toffoli.prev_q3 is not null then
                    update linked_circuit set next_q3 = gate1_id * 10 + 2 where id = div(toffoli.prev_q3, 10);
                end if;

                -- Connect the last gate to the original CNOT's next gates
                if cnot.next_q1 is not null then
                    update linked_circuit set prev_q1 = gate14_id * 10 where id = div(cnot.next_q1, 10);
                end if;
                if cnot.next_q2 is not null then
                    update linked_circuit set prev_q2 = gate14_id * 10 + 1 where id = div(cnot.next_q2, 10);
                end if;
                if cnot.next_q3 is not null then
                    update linked_circuit set prev_q3 = gate14_id * 10 + 2 where id = div(cnot.next_q3, 10);
                end if;

                -- Delete the original Toffoli and CNOT
                delete from linked_circuit where id = toffoli.id;
                delete from linked_circuit where id = cnot.id;

                found := true;
                commit;
            end if;
        end if;
    end loop;
    raise notice 'Time spent transforming Toffoli-CNOT patterns = %', clock_timestamp() - start_time;
end;$$;

-- alter procedure linked_toffoli_cnot_transform() owner to postgres; 