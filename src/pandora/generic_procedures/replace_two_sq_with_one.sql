-- does not include the replacement of global_phase
create or replace procedure fuse_single_qubit(type_1 int, type_2 int, type_replace int, param1 float, param2 float, param_replace real, my_proc_id int, nprocs int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    first_next_id bigint;
    second_next_id bigint;

    first record;
    second record;
    gate record;

    distinct_count bigint;
    distinct_existing bigint;
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
            if gate.id is null then
                continue;
            end if;

            select * into first from linked_circuit where id = gate.id;

            first_next_id :=  div(first.next_q1, 1000);
			select * into second from linked_circuit where id = first_next_id;

			if second.id is not null and second.param = param2 then
			    second_next_id := div(second.next_q1, 1000);

			    select count(*) into distinct_count from (select distinct unnest(array[second_next_id])) as it;
			    select count(*) into distinct_existing from (select id from linked_circuit where id in (second_next_id)
			                                                                               for update skip locked) as it;
			    if distinct_count != distinct_existing then
			       commit;
			       continue;
                end if;

			    -- Lock the Hadamards and CX
                select count(*) into distinct_count from (select * from linked_circuit where id in (first.id, second.id) for update skip locked) as it;
                if distinct_count != 2 then
                    continue;
                end if;

			    new_next := (first.id * 10) * 100 + first.type;

                update linked_circuit set (type, next_q1, param) = (type_replace, second.next_q1, param_replace) where id = first.id;

			    if mod(div(second.next_q1, 100), 10) = 0 then
                    update linked_circuit set prev_q1 = new_next where id = second_next_id;
                else
                    update linked_circuit set prev_q2 = new_next where id = second_next_id;
                end if;

                delete from linked_circuit where id = second.id;

			    commit;

            end if; -- end second gate match

        end loop; -- end gate loop

        pass_count = pass_count - 1;

        if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

     end loop; -- end pass loop
end;$$;
