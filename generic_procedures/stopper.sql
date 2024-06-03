create or replace procedure stopper(run_time int)
    language plpgsql
as
$$
begin
	perform pg_sleep(run_time);
	update stop_condition set stop=True;
end;$$;
