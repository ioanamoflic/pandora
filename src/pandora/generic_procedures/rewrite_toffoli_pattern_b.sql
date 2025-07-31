create or replace procedure rewrite_toffoli_pattern_b()
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

    input1_id bigint;
    input2_id bigint;
    output1_id bigint;
    output2_id bigint;

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
                              where it.type = 23 limit 1;

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
                -- Replace with the full A2 sequence
                
                -- Get the next available ID
--                 select max(id) into last_id from linked_circuit;
--                 if last_id is null then
--                     last_id := 0;
--                 end if;
                -- last_id := last_id + 1;

--               Nr gate:    1   2   3   4   5   6   7   8   9   10  11  12  13  14
--                     0: IN1────────────────X───X───X───────@───────@───@───X───X───OUT1
--                                           │   │   │       │       │   │   │   │
--  ───@───────        1: ───────@───@───────┼───┼───@───@───@───────@───┼───┼───┼───
--     │                         │   │       │   │   │   │   │       │   │   │   │
--  ───@───x──    =    2: ───X───@───@───────┼───@───@───┼───X───@───┼───┼───@───┼───
--     │   │                 │   │   │       │           │       │   │   │       │
--  ───x───@───        3: ───@───X───┼───@───@───────────X───────┼───┼───┼───────@───
--                                   │   │               │       │   │   │
--                     4: IN2────────X───X───────────────@───────X───X───X───────────OUT2

                -- Insert two Input gates
                insert into linked_circuit(type, label) values(0, toffoli.label) returning id into input1_id;
                insert into linked_circuit(type, label) values(0, toffoli.label) returning id into input2_id;

                -- Insert the new sequence of gates (A2 pattern)

                -- Gate 1: CNOT(3,2) - First gate connects to original Toffoli's previous gates
                insert into linked_circuit(type, label)  values (18, toffoli.label) returning id into gate1_id;
                -- Gate 2: Toffoli(1,2,3) - connects to gate1
                insert into linked_circuit(type, label)  values (23, toffoli.label) returning id into gate2_id;

                 -- Insert two Input gates
                insert into linked_circuit(type, label) values(1, toffoli.label) returning id into output1_id;
                insert into linked_circuit(type, label) values(1, toffoli.label) returning id into output2_id;

--                 ...

                -- update previous for all the gates
                update linked_circuit set (prev_q1, prev_q2, prev_q3) = (? ,? , ?) where id = gate1_id;

                -- update next for all the gates
                update linked_circuit set (next_q1, next_q2, next_q3) = (? ,? , ?) where id = gate1_id;

                -- Gate 3: Toffoli(1,2,4) - connects to gate2
                insert into linked_circuit values (default, gate2_id * 10 + 0, gate2_id * 10 + 0, gate2_id * 10 + 1, 23,
                                                   1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate3_id;
                -- last_id := last_id + 1;

                -- Gate 4: CNOT(3,4) - connects to gate3
                insert into linked_circuit values (default, gate3_id * 10, gate3_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate4_id;

                -- Gate 5: CNOT(3,0) - connects to gate4
                insert into linked_circuit values (default, gate4_id * 10, gate4_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate5_id;

                -- Gate 6: CNOT(2,0) - connects to gate5
                insert into linked_circuit values (default, gate5_id * 10, gate5_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate6_id;

                -- Gate 7: Toffoli(2,1,0) - connects to gate6
                insert into linked_circuit values (default, gate6_id * 10, gate6_id * 10 + 1, gate6_id * 10 + 2, 23, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate7_id;

                -- Gate 8: Toffoli(1,4,3) - connects to gate7
                insert into linked_circuit values (default, gate7_id * 10, gate7_id * 10 + 1, gate7_id * 10 + 2, 23, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate8_id;

                -- Gate 9: Toffoli(0,1,2) - connects to gate8
                insert into linked_circuit values (default, gate8_id * 10, gate8_id * 10 + 1, gate8_id * 10 + 2, 23, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate9_id;

                -- Gate 10: CNOT(2,4) - connects to gate9
                insert into linked_circuit values (default, gate9_id * 10, gate9_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate10_id;

                -- Gate 11: Toffoli(0,1,4) - connects to gate10
                insert into linked_circuit values (default, gate10_id * 10, gate10_id * 10 + 1, gate10_id * 10 + 2, 23, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate11_id;

                -- Gate 12: CNOT(0,4) - connects to gate11
                insert into linked_circuit values (default, gate11_id * 10, gate11_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate12_id;

                -- Gate 13: CNOT(2,0) - connects to gate12
                insert into linked_circuit values (default, gate12_id * 10, gate12_id * 10 + 1, null, 18, 1, 0, false, null, null, null, false, toffoli.label, false, null)
                                              returning id into gate13_id;

                -- Gate 14: CNOT(3,0) - connects to gate13 and to original CNOT's next gates
                insert into linked_circuit values (default, gate13_id * 10, gate13_id * 10 + 1, null, 18, 1, 0, false, cnot.next_q1, cnot.next_q2, cnot.next_q3, false, toffoli.label, false, null)
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