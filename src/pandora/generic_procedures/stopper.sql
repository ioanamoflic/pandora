create or replace procedure stopper(run_time real)
    language plpgsql
as
$$
begin
    delete from stop_condition where stop=True or stop=False;
	perform pg_sleep(run_time);
	insert into stop_condition values (True);
end;$$;
