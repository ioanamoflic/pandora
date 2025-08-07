create or replace procedure linked_cx_to_hhcxhh(my_proc_id int, nprocs int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    gate record;
    first record;
    second record;

    m11 record;
    m12 record;
    m13 record;
    m21 record;
    m22 record;
    m23 record;

    m11_id bigint;
    m12_id bigint;
    m13_id bigint;
    m21_id bigint;
    m22_id bigint;
    m23_id bigint;

	start_time timestamp;

    left_h_q1_id bigint;
	left_h_q2_id bigint;
	right_h_q1_id bigint;
	right_h_q2_id bigint;

    -- used for computing the links
    port_nr bigint;
    gate_type bigint;

    -- the links to the right and left
    first_port0 bigint;
    first_port1 bigint;
    first_port2 bigint;
    second_port0 bigint;
    second_port1 bigint;
    second_port2 bigint;

begin
    port_nr := 0; -- single qubit gate has a single port with index 0
    gate_type := 8; -- Hadamard

    start_time := CLOCK_TIMESTAMP();

    while pass_count > 0 loop
        for gate in
            select * from linked_circuit
                     where id % nprocs = my_proc_id
                     and type in (15, 18)
        loop
            select * into first from linked_circuit where id = gate.id for update skip locked;
            second := first;

            if first.id is null or second.id is null then
                commit;
                continue;
            end if;

            m11_id := div(first.prev_q1, 1000);
            m12_id := div(first.prev_q2, 1000);
            m21_id := div(second.next_q1, 1000);
            m22_id := div(second.next_q2, 1000);

            select * into m11 from linked_circuit where id = m11_id for update skip locked;
            select * into m12 from linked_circuit where id = m12_id for update skip locked;
            select * into m21 from linked_circuit where id = m21_id for update skip locked;
            select * into m22 from linked_circuit where id = m22_id for update skip locked;

            if m11.id is null or m12.id is null or m21.id is null or m22.id is null then
                commit;
                continue;
            end if;

            first_port0 := first.id * 1000 + 0 * 100 + first.type;
            first_port1 := first.id * 1000 + 1 * 100 + first.type;
            second_port0 := second.id * 1000 + 0 * 100 + second.type;
            second_port1 := second.id * 1000 + 1 * 100 + second.type;

            insert into linked_circuit(prev_q1, type, param, next_q1, visited, label) values (first.prev_q1, gate_type, 1, first_port1, my_proc_id, first.label)
                                                          returning id into left_h_q1_id;

            insert into linked_circuit(prev_q1, type, param, next_q1, visited, label) values (first.prev_q2, gate_type, 1, first_port0, my_proc_id, first.label)
                                                          returning id into left_h_q2_id;

            insert into linked_circuit(prev_q1, type, param, next_q1, visited, label) values (second_port1, gate_type, 1, first.next_q1, my_proc_id, first.label)
                                                          returning id into right_h_q1_id;

            insert into linked_circuit(prev_q1, type, param, next_q1, visited, label) values (second_port0, gate_type, 1, first.next_q2,my_proc_id, first.label)
                                                          returning id into right_h_q2_id;

            -- These are the links that the margins and CNOT should use
            -- First and Second are practically updated because of the new Hadamards
            -- But we keep them referring to the CX gates
            -- Update the first and second ports
            first_port0 := left_h_q1_id * 1000 + port_nr * 100 + gate_type;
            first_port1 := left_h_q2_id * 1000 + port_nr * 100 + gate_type;
            second_port0 := right_h_q1_id * 1000 + port_nr * 100 + gate_type;
            second_port1 := right_h_q2_id * 1000 + port_nr * 100 + gate_type;

            -- Update the CNOT: flip the switch value and set visited
            update linked_circuit set (prev_q1, prev_q2, next_q1, next_q2, switch, visited) = (first_port1, first_port0, second_port1, second_port0, not first.switch, my_proc_id) where id = first.id;

            if mod(div(first.prev_q1, 100), 10) = 0 then
                update linked_circuit set next_q1 = first_port0 where id = m11_id;
            else
                update linked_circuit set next_q2 = first_port0 where id = m11_id;
            end if;

            if mod(div(first.prev_q2, 100), 10) = 0 then
                update linked_circuit set next_q1 = first_port1 where id = m12_id;
            else
                update linked_circuit set next_q2 = first_port1 where id = m12_id;
            end if;

            if mod(div(second.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = second_port0 where id = m21_id;
            else
                update linked_circuit set prev_q2 = second_port0 where id = m21_id;
            end if;

            if mod(div(second.next_q2, 100), 10) = 0 then
                update linked_circuit set prev_q1 = second_port1 where id = m22_id;
            else
                update linked_circuit set prev_q2 = second_port1 where id = m22_id;
            end if;

            commit; -- release locks

        end loop; -- end gate loop

        if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

        pass_count = pass_count - 1;

    end loop; -- end pass loop
end;$$;

