-- does not include the replacement of global_phase
create or replace procedure fuse_single_qubit(type_1 int, type_2 int, type_replace int, param1 float, param2 float, param_replace float, my_proc_id int, nprocs int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    second_next_id bigint;
    first_prev_id bigint;

    first record;
    second record;
    gate record;

    a record;
    b record;

    new_next bigint;
    new_prev bigint;

    start_time timestamp;

begin
    start_time := clock_timestamp();

	 while pass_count > 0 loop
        for gate in
            select * from linked_circuit
            where
            type=type_1
            and get_type_from_link(next_q1) = type_2
            and param=param1
        loop
            select * into first from linked_circuit where id = gate.id for update skip locked;
            select * into second from linked_circuit where id = get_id_from_link(first.next_q1) for update skip locked;

            if first.id is null
                or second.id is null
            then
                commit;
                continue;
            end if;

            if second.param != param2
                or first.param != param1
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

            new_next := create_link(first.id, 0, type_replace::smallint);
            new_prev := create_link(first.id, 0, type_replace::smallint);

            update linked_circuit set (type, next_q1, param) = (type_replace, second.next_q1, param_replace) where id = first.id;

            if get_port_from_link(second.next_q1) = 0 then
                update linked_circuit set prev_q1 = new_next where id = second_next_id;
            else
                update linked_circuit set prev_q2 = new_next where id = second_next_id;
            end if;

            if get_port_from_link(first.prev_q1) = 0 then
                update linked_circuit set next_q1 = new_prev where id = first_prev_id;
            else
                update linked_circuit set next_q2 = new_prev where id = first_prev_id;
            end if;

            delete from linked_circuit where id = second.id;

            commit;

        end loop; -- end gate loop

        pass_count = pass_count - 1;

	    if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

     end loop; -- end pass loop
end;$$;
