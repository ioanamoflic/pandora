create or replace procedure linked_cx_to_hhcxhh(sys_range int, run_nr int)
    language plpgsql
as
$$
declare
    cx record;
    cx_prev_q1_id bigint;
	cx_prev_q2_id bigint;
	cx_next_q1_id bigint;
	cx_next_q2_id bigint;
    left_h_q1_id bigint;
	left_h_q2_id bigint;
	right_h_q1_id bigint;
	right_h_q2_id bigint;
    distinct_count bigint;
    distinct_existing int;
    modulus_left_cx_q1 varchar(8);
    modulus_left_cx_q2 varchar(8);
	modulus_right_cx_q1 varchar(8);
	modulus_right_cx_q2 varchar(8);
    left_q1_id bigint;
    left_q2_id bigint;
    right_q1_id bigint;
    right_q2_id bigint;
    cx_id_ctrl bigint;
    cx_id_tgt bigint;
	start_time timestamptz;
    stop boolean;
begin
    start_time := clock_timestamp();

    while run_nr > 0 loop
        select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;
        select * into cx from (select * from linked_circuit_qubit lc tablesample system_rows(sys_range)) as it where type = 'CXPowGate' for update skip locked limit 1;
        if cx.id is not null then
            cx_prev_q1_id := div(cx.prev_q1, 10);
            cx_prev_q2_id := div(cx.prev_q2, 10);
            cx_next_q1_id := div(cx.next_q1, 10);
            cx_next_q2_id := div(cx.next_q2, 10);

            modulus_left_cx_q1 := 'next_q' || mod(cx.prev_q1, 10) + 1;
            modulus_left_cx_q2 := 'next_q' || mod(cx.prev_q2, 10) + 1;
            modulus_right_cx_q1 := 'prev_q' || mod(cx.next_q1, 10) + 1;
            modulus_right_cx_q2 := 'prev_q' || mod(cx.next_q2, 10) + 1;
            select count(*) into distinct_count from (select distinct unnest(array[cx_prev_q1_id, cx_prev_q2_id, cx_next_q1_id, cx_next_q2_id])) as it;
            select count(*) into distinct_existing from
                 (select * from linked_circuit_qubit where id in (cx_prev_q1_id, cx_prev_q2_id, cx_next_q1_id, cx_next_q2_id) for update skip locked) as it;

            if distinct_count = distinct_existing then
                cx_id_ctrl := cx.id * 10;
                cx_id_tgt := cx.id * 10 + 1;
                insert into linked_circuit_qubit values (DEFAULT, cx.prev_q1, null, null, 'HPowGate', 1, false, cx_id_tgt, null, null, false, cx.label, false, null, cx.qub_1, null, null)
                                                              returning id into left_h_q1_id;
                insert into linked_circuit_qubit values (DEFAULT, cx.prev_q2, null, null, 'HPowGate', 1, false, cx_id_ctrl, null, null, false, cx.label, false, null, cx.qub_2, null, null)
                                                              returning id into left_h_q2_id;
                left_q1_id := left_h_q1_id * 10;
                left_q2_id := left_h_q2_id * 10;
                insert into linked_circuit_qubit values (DEFAULT, cx_id_tgt, null, null, 'HPowGate', 1, false, cx.next_q1, null, null, false, cx.label, false, null, cx.qub_1, null, null)
                                                              returning id into right_h_q1_id;
                insert into linked_circuit_qubit values (DEFAULT, cx_id_ctrl, null, null, 'HPowGate', 1, false, cx.next_q2, null, null, false, cx.label, false, null, cx.qub_2, null, null)
                                                              returning id into right_h_q2_id;
                right_q1_id := right_h_q1_id * 10;
                right_q2_id := right_h_q2_id * 10;

                update linked_circuit_qubit set (qub_1, qub_2, prev_q1, prev_q2, next_q1, next_q2, switch, visited) = (cx.qub_2, cx.qub_1, left_q2_id, left_q1_id, right_q2_id, right_q1_id, not cx.switch, true) where id = cx.id;
                execute 'update linked_circuit_qubit set ' || modulus_left_cx_q1 || ' = $1 where id = $2' using left_q1_id, cx_prev_q1_id;
                execute 'update linked_circuit_qubit set ' || modulus_left_cx_q2 || ' = $1 where id = $2' using left_q2_id, cx_prev_q2_id;
                execute 'update linked_circuit_qubit set ' || modulus_right_cx_q1 || ' = $1 where id = $2' using right_q1_id, cx_next_q1_id;
                execute 'update linked_circuit_qubit set ' || modulus_right_cx_q2 || ' = $1 where id = $2' using right_q2_id, cx_next_q2_id;
                run_nr = run_nr - 1;
            end if;
            commit;
            perform pg_sleep(0.1);
        end if;
    end loop;
    raise notice 'Time spent for all cx -> hhcxhh =%', clock_timestamp() - start_time;
end;$$;

