create or replace procedure memorize_cx_ids()
    language plpgsql
as
$$
declare
   t_curs cursor for select * from linked_circuit;
   t_row linked_circuit%rowtype;
begin
    for t_row in t_curs loop
        if t_row.type in (15, 18) then
            insert into mem_cx values (t_row.id);
        end if;
    end loop;

    -- shuffle by creating a new table
    create temp table temp_table as
    select * from mem_cx order by random();

    drop table mem_cx;

    alter table temp_table rename to mem_cx;
end;
$$