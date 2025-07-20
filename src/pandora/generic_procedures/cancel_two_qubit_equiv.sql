create or replace procedure cancel_two_qubit_equiv(type_1 int, type_2 int, parameter float, sys_range int, run_nr int)
    language plpgsql
as
$$
declare
	modulus_first_prev_q1 varchar(8);
	modulus_first_prev_q2 varchar(8);
	modulus_second_next_q1 varchar(8);
	modulus_second_next_q2 varchar(8);
    first_id_plus_one bigint;
    first_id_plus_zero bigint;
	first_prev_q1 bigint;
	first_prev_q2 bigint;
    second_next_q1 bigint;
	second_next_q2 bigint;
    distinct_count int;
    distinct_existing int;
    first record;
    second record;
    stop boolean;
    compare record;
    rounds_missed smallint := 0;
    is_missed_round boolean;
--     max_missed int;
begin
--     insert into max_missed_rounds values (0);
	while run_nr > 0 loop

        if rounds_missed >= 1500 then
            exit;
        end if;

--         select max(mm.missed) into max_missed from max_missed_rounds as mm;
--         if rounds_missed > max_missed then
--             insert into max_missed_rounds values (rounds_missed);
--         end if;

	    select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;

	    is_missed_round := true;
        for first in
            (select * from (select * from linked_circuit lc tablesample system_rows(sys_range)) as it
    	                    where it.type=type_1
                            and it.next_q1 / 10 = it.next_q2 / 10 -- two gates sharing the same wires
                            and it.param = parameter for update skip locked)
        loop
            if first.id is not null then
                first_id_plus_one := first.id * 10 + 1;
                first_id_plus_zero := first.id * 10;
                select * into second from linked_circuit where prev_q1 = first_id_plus_zero and prev_q2 = first_id_plus_one and switch = first.switch for update skip locked;

                compare := second;
                if compare.id is null or compare.type != type_2 or compare.param != parameter then
                    -- LOOK BACKWARD (second, first)
                    -- first becomes second
                    second := first;
                    -- select a different first from the database - LOOK BACKWARD
                    select * into first from linked_circuit where next_q1 = first_id_plus_zero and next_q2 = first_id_plus_one and switch = first.switch for update skip locked;

                    compare := first;
                end if;

                if compare.id is not null and compare.type=type_2 and compare.param = parameter then
                    -- LOOK FORWARD (first, second)
                    first_prev_q1 := div(first.prev_q1, 10);
                    first_prev_q2 := div(first.prev_q2, 10);
                    second_next_q1 := div(second.next_q1, 10);
                    second_next_q2 := div(second.next_q2, 10);

                    select count(*) into distinct_count from (select distinct unnest(array[first_prev_q1, first_prev_q2, second_next_q1, second_next_q2])) as it;
                    select count(*) into distinct_existing from
                    (select * from linked_circuit where id in (first_prev_q1, first_prev_q2, second_next_q1, second_next_q2) for update skip locked) as it;

                    if distinct_count = distinct_existing then
                        modulus_first_prev_q1 := 'next_q' || mod(first.prev_q1, 10) + 1;
                        modulus_first_prev_q2 := 'next_q' || mod(first.prev_q2, 10) + 1;
                        modulus_second_next_q1 := 'prev_q' || mod(second.next_q1, 10) + 1;
                        modulus_second_next_q2 := 'prev_q' || mod(second.next_q2, 10) + 1;

                        execute 'update linked_circuit set ' || modulus_first_prev_q1 || ' = $1 where id = $2' using second.next_q1, first_prev_q1;
                        execute 'update linked_circuit set ' || modulus_first_prev_q2 || ' = $1 where id = $2' using second.next_q2, first_prev_q2;
                        execute 'update linked_circuit set ' || modulus_second_next_q1 || ' = $1 where id = $2' using first.prev_q1, second_next_q1;
                        execute 'update linked_circuit set ' || modulus_second_next_q2 || ' = $1 where id = $2' using first.prev_q2, second_next_q2;

                        delete from linked_circuit lc where lc.id in (first.id, second.id);
                        run_nr = run_nr - 1;

                        is_missed_round = false;
                        rounds_missed = 0;

                    end if;
                end if;
                commit;

                if run_nr = 0 then
                    exit;
                end if;

            end if;
		end loop;

	    if is_missed_round = true then
            rounds_missed := rounds_missed + 1;
        end if;

	end loop;
end;$$;
