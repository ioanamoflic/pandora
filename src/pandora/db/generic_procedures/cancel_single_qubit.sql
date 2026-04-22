create or replace procedure cancel_single_qubit(type_1 int, type_2 int, param_1 float, param_2 float, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    first_prev_id bigint;
    second_next_id bigint;

    gate record;
    first record;
    second record;

    a record;
    b record;

	start_time timestamp;

begin
    start_time := clock_timestamp();

	 while pass_count > 0 loop
        for gate in
            select * from linked_circuit
                     where
                       type = type_1
                       and param = param_1
                       and get_type_from_link(next_q1) = type_2
        loop
            select * into first from linked_circuit where id = gate.id for update skip locked;
            select * into second from linked_circuit where id = get_id_from_link(first.next_q1) for update skip locked;

            if first.id is null
                or second.id is null
            then
                commit;
                continue;
            end if;

            if first.param != param_1
                or second.param != param_2
                or first.type != type_1
                or second.type != type_2
            then
                commit;
                continue;
            end if;

            if get_id_from_link(second.prev_q1) != first.id
			    or get_id_from_link(first.next_q1) != second.id
            then
                commit;
                continue;
            end if;

            first_prev_id := get_id_from_link(first.prev_q1);
            second_next_id := get_id_from_link(second.next_q1);

            select * into a from linked_circuit where id = first_prev_id for update skip locked;
            select * into b from linked_circuit where id = second_next_id for update skip locked;

            if a.id is null
                or b.id is null
            then
                commit;
                continue;
            end if;

            if get_port_from_link(first.prev_q1) = 0 then
                update linked_circuit set next_q1 = second.next_q1 where id = first_prev_id;
            else
                update linked_circuit set next_q2 = second.next_q1 where id = first_prev_id;
            end if;

            if get_port_from_link(second.next_q1) = 0 then
                update linked_circuit set prev_q1 = first.prev_q1 where id = second_next_id;
            else
                update linked_circuit set prev_q2 = first.prev_q1 where id = second_next_id;
            end if;

            delete from linked_circuit where id in (first.id, second.id);

            commit; -- release the locks

        end loop; -- end gate loop

	    pass_count = pass_count - 1;

	    if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

    end loop; -- end pass loop
end;$$;
