do $$
declare
    r record;
    total bigint := 0;
    row_count bigint;
begin
    for r in
        select table_schema, table_name
        from information_schema.tables
        where table_type = 'BASE TABLE'
        and table_schema not in ('pg_catalog', 'information_schema')
    loop
        execute format('select count(*) from %I.%I where %I.%I.type not in (0, 1)', r.table_schema, r.table_name, r.table_schema, r.table_name) into row_count;
        -- raise notice 'Table %.%: % rows', r.table_schema, r.table_name, row_count;
        total := total + row_count;
    end loop;
    raise notice 'Total: %', total;
end $$;