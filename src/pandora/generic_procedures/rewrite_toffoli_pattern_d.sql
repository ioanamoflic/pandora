create or replace procedure rewrite_toffoli_pattern_d()
    language plpgsql
as
$$
declare
    toffoli record;
    cnot record;

    -- New gates to insert (based on A2 circuit)
    gate1_id bigint;
    gate2_id bigint;
    gate3_id bigint;

    -- utility variables
    found boolean = true;
begin
    while found = true loop
        found := false;

        -- Find a Toffoli gate (type = 23)
        select * into toffoli from linked_circuit as it
                              where it.type = 23;

        if toffoli.id is not null then
            -- Find the next gate to see if it's a CNOT
            -- Check multiple possible connections
            select * into cnot from linked_circuit as it
                               where (it.id = toffoli.next_q1 / 10 or 
                                     it.id = toffoli.next_q2 / 10 or 
                                     it.id = toffoli.next_q3 / 10)
                                 and it.type = 18;

            if cnot.id is not null then
                -- We found Toffoli followed by CNOT
                -- Replace with the full D2 sequence

                -- Insert the new sequence of gates (D2 pattern)

                -- Gate 1: cnot(3,0) - First gate connects to original Toffoli's previous gates
                insert into linked_circuit(type, label)  values (18, toffoli.label) returning id into gate1_id;
                -- Gate 2: Toffoli(0,1,2) - connects to gate1
                insert into linked_circuit(type, label)  values (23, toffoli.label) returning id into gate2_id;
                -- Gate 3: TOFFOLI(0,3,2) - connects to gate2
                insert into linked_circuit(type, label)  values (23, toffoli.label) returning id into gate3_id;

                -- Gate1 connections
                update linked_circuit set (prev_q1, prev_q2, prev_q3) = (toffoli.prev_q2, cnot.prev_q2, null) where id = gate1_id;
                update linked_circuit set (next_q1, next_q2, next_q3) = (gate2_id * 10 + 1, gate3_id * 10 + 0, null) where id = gate1_id;

                -- Gate2 connections
                update linked_circuit set (prev_q1, prev_q2, prev_q3) = (toffoli.prev_q1, gate1_id * 10 + 0, toffoli.prev_q3) where id = gate2_id;
                update linked_circuit set (next_q1, next_q2, next_q3) = (gate3_id * 10 + 0, cnot.next_q1, gate3_id * 10 + 1) where id = gate2_id;

                -- Gate3 connections
                update linked_circuit set (prev_q1, prev_q2, prev_q3) = (gate2_id * 10 + 0, gate2_id * 10 + 1, gate1_id * 10 + 0) where id = gate3_id;
                update linked_circuit set (next_q1, next_q2, next_q3) = (toffoli.next_q1, toffoli.next_q3, cnot.next_q2) where id = gate3_id;

                -- Delete the original Toffoli and CNOT
                delete from linked_circuit where id = toffoli.id;
                delete from linked_circuit where id = cnot.id;

                commit;
            end if;
        end if;
    end loop;
end;$$;

-- alter procedure linked_toffoli_cnot_transform() owner to postgres; 