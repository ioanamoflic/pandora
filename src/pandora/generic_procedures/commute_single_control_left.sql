create or replace procedure commute_single_control_left(single_type int, parameter float, my_proc_id int, nprocs int, pass_count int, timeout int)
   language plpgsql
as
$$
declare
    first record;
    second record;
    gate record;

    cx_next_q1 bigint;
    cx_prev_q1 bigint;
    sg_prev_id bigint;
    cx_next_q1_id bigint;

    new_next_for_sq bigint;
    new_prev_for_sq bigint;

    a record;
    b record;

    start_time timestamp with time zone;

    h_type smallint;
    controlled_types smallint[];

begin

    select id into h_type from gate_types where name = 'h';
    select array_agg(id) into controlled_types from gate_types where name in ('cx', 'cxpow', 'cz', 'czpow');

    start_time := clock_timestamp();

	while pass_count > 0 loop
        for gate in
            select * from linked_circuit
                     where
                     type = any(controlled_types)
                     and get_type_from_link(prev_q1) = single_type
        loop
            select * into second from linked_circuit where id = gate.id for update skip locked;
            select * into first from linked_circuit where id = get_id_from_link(second.prev_q1) for update skip locked;

            if first.id is null
                or second.id is null
            then
                commit;
                continue;
            end if;

            if second.type != all(controlled_types)
                or first.param != parameter
                or first.type != single_type
                or get_id_from_link(first.next_q1) != second.id
                or get_id_from_link(second.prev_q1) != first.id
            then
                commit;
                continue;
            end if;

            sg_prev_id := get_id_from_link(first.prev_q1);
            cx_next_q1_id := get_id_from_link(second.next_q1);

            select * into a from linked_circuit where id = sg_prev_id for update skip locked;
            select * into b from linked_circuit where id = cx_next_q1_id for update skip locked;

            if a.id is null or b.id is null then
                commit;
                continue;
            end if;

            cx_next_q1 = second.next_q1;
            cx_prev_q1 = second.prev_q1;

            new_next_for_sq := create_link(second.id, 0, second.type);
            new_prev_for_sq := create_link(first.id, 0, first.type);

            if get_port_from_link(first.prev_q1) = 0 then
                update linked_circuit set next_q1 = new_next_for_sq where id = sg_prev_id;
            else
                update linked_circuit set next_q2 = new_next_for_sq where id = sg_prev_id;
            end if;

            if get_port_from_link(second.next_q1) = 0 then
                update linked_circuit set prev_q1 = new_prev_for_sq where id = cx_next_q1_id;
            else
                update linked_circuit set prev_q2 = new_prev_for_sq where id = cx_next_q1_id;
            end if;

            update linked_circuit set (next_q1, prev_q1) = (new_prev_for_sq, first.prev_q1) where id = second.id;
            update linked_circuit set (next_q1, prev_q1) = (cx_next_q1, new_next_for_sq) where id = first.id;

            commit; -- release locks

        end loop; -- end gate loop

	    if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

        pass_count = pass_count - 1;

    end loop; -- end pass loop

end;$$;
