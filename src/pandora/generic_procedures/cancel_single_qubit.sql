create or replace procedure cancel_single_qubit(type_1 int, type_2 int, param_1 float, param_2 float, my_proc_id int, nprocs int, pass_count int, timeout int)
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
    start_time := CLOCK_TIMESTAMP();

	 while pass_count > 0 loop

        for gate in
            select * from linked_circuit
                     where
                       id % nprocs = my_proc_id
                       and type = type_1
                       and param = param_1
                       and mod(next_q1, 100) = type_2
        loop
            select * into first from linked_circuit where id = gate.id for update skip locked;
            select * into second from linked_circuit where id = div(first.next_q1, 1000) for update skip locked;

            if first.id is null or second.id is null then
                commit;
                continue;
            end if;

            if second.param != param_2 or second.type != type_2 then
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

            if mod(div(first.prev_q1, 100), 10) = 0 then
                update linked_circuit set next_q1 = second.next_q1 where id = first_prev_id;
            else
                update linked_circuit set next_q2 = second.next_q1 where id = first_prev_id;
            end if;

            if mod(div(second.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = first.prev_q1 where id = second_next_id;
            else
                update linked_circuit set prev_q2 = first.prev_q1 where id = second_next_id;
            end if;

            delete from linked_circuit where id in (first.id, second.id);

            commit; -- release the locks

            if extract(epoch from (clock_timestamp() - start_time)) > timeout then
                exit;
            end if;

        end loop; -- end gate loop

	    pass_count = pass_count - 1;

--         if extract(epoch from (clock_timestamp() - start_time)) > timeout then
--             exit;
--         end if;

    end loop; -- end pass loop
end;$$;
