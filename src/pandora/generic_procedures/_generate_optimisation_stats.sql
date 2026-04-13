create or replace procedure generate_optimisation_stats(sleep_for float, logid int, timeout int)
    language plpgsql
as
$$
declare
    total int;
    t_cnt int;
    s_cnt int;
    h_cnt int;
    cx_cnt int;
    x_cnt int;
    count int := 0;

    start_time timestamp;

begin
    start_time := CLOCK_TIMESTAMP();

    while true loop
        count := count + 1;

        select count(*) into total from linked_circuit;
        select count(*) into t_cnt from linked_circuit where type in (29, 30);
        select count(*) into s_cnt from linked_circuit where type in (27, 28);
        select count(*) into h_cnt from linked_circuit where type=8;
        select count(*) into x_cnt from linked_circuit where type=9;
        select count(*) into cx_cnt from linked_circuit where type=18;

        insert into optimization_results(id, logger_id, total_count, t_count, s_count, h_count, cx_count, x_count)
        values (count, logid, total, t_cnt, s_cnt, h_cnt, cx_cnt, x_cnt);

        perform pg_sleep(sleep_for);

    	commit;

        if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

	end loop;
end;$$;
