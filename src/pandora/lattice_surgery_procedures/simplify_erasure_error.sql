create or replace procedure simplify_erasure_error(type_1 int, type_2 int, sys_range int, run_nr int)
    language plpgsql
as
$$
declare
    first_next_id_q1 bigint;
    first_next_id_q2 bigint;

    third_next_id_q1 bigint;
    third_next_id_q2 bigint;

    second_next_id_q1 bigint;
    second_prev_id_q1 bigint;

    modulus_next_q1 varchar(8);
    modulus_next_q2 varchar(8);

    first record;
    second record;
    third record;
    distinct_count bigint;
    distinct_existing bigint;
    stop boolean;
begin
	while run_nr > 0 loop
	    select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;
    	select * into first from (select * from linked_circuit lc tablesample system_rows(sys_range)) as it where it.type=type_1 for update skip locked limit 1;

    	if first.id is not null then
    	    first_next_id_q1 :=  div(first.next_q1, 10);
    	    first_next_id_q2 :=  div(first.next_q2, 10);

			select * into second from linked_circuit where id = first_next_id_q1;
    	    if second.type != type_2 then
                select * into second from linked_circuit where id = first_next_id_q2;
            end if;

    	    second_next_id_q1 := div(second.next_q1, 10);
		    second_prev_id_q1 := div(second.prev_q1, 10);

			select * into third from linked_circuit where id = second_next_id_q1;
    	    third_next_id_q1 :=  div(third.next_q1, 10);
    	    third_next_id_q2 :=  div(third.next_q2, 10);

			if third.id is not null and third.type=type_1 and
			   second.id is not null and second.type=type_2 and
			   second_next_id_q1 = third.id and
			   second_prev_id_q1 = first.id and (
               first_next_id_q1 = third.id or
			   first_next_id_q2 = third.id) then

			    select count(*) into distinct_count from (select distinct unnest(array[second.id, third.id,
			        third_next_id_q1, third_next_id_q2])) as it;
			    select count(*) into distinct_existing from (select id from linked_circuit where id in (second.id, third.id,
			        third_next_id_q1, third_next_id_q2)
			                                                                               for update skip locked) as it;
			    if distinct_count = distinct_existing then
			        modulus_next_q1 := 'prev_q' || mod(third.next_q1, 10) + 1;
			        modulus_next_q2 := 'prev_q' || mod(third.next_q2, 10) + 1;

			        execute 'update linked_circuit set ' || modulus_next_q1 || ' = $1 where id = $2' using first.id * 10, third_next_id_q1;
			        execute 'update linked_circuit set ' || modulus_next_q2 || ' = $1 where id = $2' using first.id * 10 + 1, third_next_id_q2;

                    update linked_circuit set (next_q1, next_q2) = (third.next_q1, third.next_q2) where id = first.id;
                    delete from linked_circuit lc where lc.id in (second.id, third.id);
			        run_nr = run_nr - 1;
                end if;
			end if;
    	    commit;
		end if;
	end loop;
end;$$;
