create or replace procedure replace_two_qubit(type_1 varchar(8), type_2 varchar(8), type_replace_1 varchar(8), sys_range int, run_nr int)
    language plpgsql
as
$$
declare
    first_next_id int;
    second_next_id int;
    modulus_next varchar(8);
    first record;
    second record;
    distinct_count int;
    distinct_existing int;
    stop boolean;
begin
	while run_nr > 0 loop
	    select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;
    	select * into first from (select * from linked_circuit lc tablesample bernoulli(sys_range)) as it where it.type=type_1 for update skip locked limit 1;

    	if first.id is not null then
    	    first_next_id :=  div(first.next_q1, 10);
			select * into second from linked_circuit where id = first_next_id;

			if second.id is not null and second.type=type_2 then
			    second_next_id := div(second.next_q1, 10);

			    select count(*) into distinct_count from (select distinct unnest(array[second.id, second_next_id])) as it;
			    select count(*) into distinct_existing from (select id from linked_circuit where id in (second.id, second_next_id)
			                                                                               for update skip locked) as it;
			    if distinct_count = distinct_existing then
			        modulus_next := 'prev_q' || mod(second.next_q1, 10) + 1;

			        update linked_circuit set (type, next_q1) = (type_replace_1, second.next_q1) where id = first.id;
			        execute 'update linked_circuit set ' || modulus_next || ' = $1 where id = $2' using first.id * 10, second_next_id;

                    delete from linked_circuit lc where lc.id = second.id;
			        run_nr = run_nr - 1;
                end if;
			end if;
    	    commit;
		end if;
	end loop;
end;$$;
