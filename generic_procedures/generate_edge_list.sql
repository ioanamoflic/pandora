create or replace procedure generate_edge_list()
    language plpgsql
as
$$
declare
   t_curs cursor for select * from linked_circuit;
   t_row linked_circuit%rowtype;
   source_id bigint;
   target_q1_id bigint;
   target_q2_id bigint;
   global_in bigint;
   global_out bigint;
begin
    global_in = (select max(id) from linked_circuit) + 1;
    global_out = (select max(id) from linked_circuit) + 2;

    for t_row in t_curs loop
        source_id := t_row.id;
        if t_row.type = 'In' then
            insert into edge_list values (global_in, source_id);
        end if;
        if t_row.type = 'Out' then
            insert into edge_list values (source_id, global_out);
        end if;
        --- single qubit gate
        if t_row.next_q1 is not null and t_row.next_q2 is null then
            target_q1_id := div(t_row.next_q1, 10);
            insert into edge_list values (source_id, target_q1_id);
        else
            --- two qubit gate
            if t_row.next_q1 is not null and t_row.next_q2 is not null and t_row.next_q3 is null then
                target_q1_id := div(t_row.next_q1, 10);
                target_q2_id := div(t_row.next_q2, 10);
                insert into edge_list values (source_id, target_q1_id);
                insert into edge_list values (source_id, target_q2_id);
            end if;
        end if;
    end loop;
end;
$$