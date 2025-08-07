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

    start_time timestamp;

begin
    start_time := CLOCK_TIMESTAMP();

	 while pass_count > 0 loop

        for gate in
            select * from linked_circuit
            where id % nprocs = my_proc_id
            and type=type_1
            and mod(next_q1, 100) = type_2
            and param=param1
        loop
            select * into first from linked_circuit where id = gate.id for update skip locked;
            select * into second from linked_circuit where id = div(first.next_q1, 1000) for update skip locked;

            if first.id is null or second.id is null then
                commit;
                continue;
            end if;

			if second.param != param2 or second.type != type_2 or div(second.prev_q1, 1000) != first.id then
			    commit;
			    continue;
			end if;

            first_prev_id := div(first.prev_q1, 1000);
            second_next_id := div(second.next_q1, 1000);

            select * into a from linked_circuit where id = first_prev_id for update skip locked;
            select * into b from linked_circuit where id = second_next_id for update skip locked;

            if a.id is null or b.id is null then
                commit;
                continue;
            end if;

            new_next := (first.id * 10) * 100 + type_replace;

            update linked_circuit set (type, next_q1, param) = (type_replace, second.next_q1, param_replace) where id = first.id;

            if mod(div(second.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = new_next where id = second_next_id;
            else
                update linked_circuit set prev_q2 = new_next where id = second_next_id;
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
