create or replace procedure for_loop()
    language plpgsql
as
$$
declare
    id int;
begin
     for i in 1..5 loop
         select lc.id into id from linked_circuit lc tablesample bernoulli(5);
         raise notice 'id=%', id;
    end loop;
end;$$;

