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

    h_type smallint;
    paulix_type smallint;
    cx_types smallint[];
    s_types smallint[];
    t_types smallint[];
    rz_type smallint;

begin
    start_time := CLOCK_TIMESTAMP();

    select id into h_type from gate_types where name = 'h';
    select id into paulix_type from gate_types where name = 'paulix';
    select id into rz_type from gate_types where name = 'zpow';

    select array_agg(id) into cx_types from gate_types where name in ('cx', 'cxpow');
    select array_agg(id) into s_types from gate_types where name in ('s', 'sdag');
    select array_agg(id) into t_types from gate_types where name in ('t', 'tdag');

    while true loop
        count := count + 1;

        select count(*) into total from linked_circuit;
        select count(*) into t_cnt from linked_circuit where type=any(t_types) or type=rz_type and param in (0.25, -0.25);
        select count(*) into s_cnt from linked_circuit where type=any(s_types) or type=rz_type and param in (0.5, -0.5);
        select count(*) into h_cnt from linked_circuit where type=h_type;
        select count(*) into x_cnt from linked_circuit where type=paulix_type;
        select count(*) into cx_cnt from linked_circuit where type=any(cx_types);

        insert into optimization_results(id, logger_id, total_count, t_count, s_count, h_count, cx_count, x_count)
        values (count, logid, total, t_cnt, s_cnt, h_cnt, cx_cnt, x_cnt);

        perform pg_sleep(sleep_for);

    	commit;

        if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

	end loop;
end;$$;
