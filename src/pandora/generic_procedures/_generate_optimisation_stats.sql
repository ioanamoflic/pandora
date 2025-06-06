create or replace procedure generate_optimisation_stats(sleep_for float, logid int)
    language plpgsql
as
$$
declare
    stop boolean;
    total int;
    t_cnt int;
    s_cnt int;
    h_cnt int;
    cx_cnt int;
    x_cnt int;
    count int := 0;
begin
    while true loop

        select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;

        count := count + 1;

        select count(*) into total from linked_circuit;
        select count(*) into t_cnt from linked_circuit where type=7 and param in (0.25, -0.25);
        select count(*) into s_cnt from linked_circuit where type=7 and param in (0.5, -0.5);
        select count(*) into h_cnt from linked_circuit where type=8;
        select count(*) into x_cnt from linked_circuit where type=9;
        select count(*) into cx_cnt from linked_circuit where type=18;

        insert into optimization_results(id, logger_id, total_count, t_count, s_count, h_count, x_count, cx_count)
        values (count, logid, total, t_cnt, s_cnt, h_cnt, x_cnt, cx_cnt);

        perform pg_sleep(sleep_for);

    	commit;
	end loop;
end;$$;
