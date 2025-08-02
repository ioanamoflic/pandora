create or replace procedure linked_hhcxhh_to_cx_seq(sys_range real, run_nr int)
    language plpgsql
as
$$
declare
    cx record;
    cx_prev_q1_id bigint;
	cx_prev_q2_id bigint;
	cx_next_q1_id bigint;
	cx_next_q2_id bigint;
    left_q1 record;
    left_q2 record;
    right_q1 record;
    right_q2 record;
    cx_id_ctrl bigint;
    cx_id_tgt bigint;
    left_q1_id bigint;
	left_q2_id bigint;
	right_q1_id bigint;
	right_q2_id bigint;
begin

    while run_nr > 0 loop
        for cx in
            select * from linked_circuit where type in (15, 18)
            and prev_q1 % 100 = 8 and prev_q2 % 100 = 8
            and next_q1 % 100 = 8 and next_q2 % 100 = 8
--             and prev_q1 % 10 = 0 and prev_q2 % 10 = 0
--             and next_q1 % 10 = 0 and next_q2 % 10 = 0
        loop
            if cx.id is not null then

                -- left gates on qubits 1,2
                cx_prev_q1_id := div(cx.prev_q1, 1000);
                cx_prev_q2_id := div(cx.prev_q2, 1000);
                cx_next_q1_id := div(cx.next_q1, 1000);
                cx_next_q2_id := div(cx.next_q2, 1000);

                select * into left_q1 from linked_circuit where id=cx_prev_q1_id;
                select * into left_q2 from linked_circuit where id=cx_prev_q2_id;
                select * into right_q1 from linked_circuit where id=cx_next_q1_id;
                select * into right_q2 from linked_circuit where id=cx_next_q2_id;

                if left_q1.type = 8 and left_q2.type = 8 and right_q1.type = 8 and right_q2.type = 8 then

                    left_q1_id := div(left_q1.prev_q1, 1000);
                    left_q2_id := div(left_q2.prev_q1, 1000);
                    right_q1_id := div(right_q1.next_q1, 1000);
                    right_q2_id := div(right_q2.next_q1, 1000);


                    -- compute new link_ids for neighbouring gates
                    cx_id_ctrl := (cx.id * 10 + 0) * 100 + cx.type;
                    cx_id_tgt  := (cx.id * 10 + 1) * 100 + cx.type;
--                     cx_id_ctrl := cx.id * 10;
--                     cx_id_tgt := cx.id * 10 + 1;

                    --- Works only for ports 1 and 2. not working for port 3

                    if mod(div(left_q1.prev_q1, 100), 10) = 0 then
                        update linked_circuit set next_q1 = cx_id_tgt where id = left_q1_id;
                    else
                        update linked_circuit set next_q2 = cx_id_tgt where id = left_q1_id;
                    end if;

                    if mod(div(left_q2.prev_q1, 100), 10) = 0 then
                        update linked_circuit set next_q1 = cx_id_ctrl where id = left_q2_id;
                    else
                        update linked_circuit set next_q2 = cx_id_ctrl where id = left_q2_id;
                    end if;

                    if mod(div(right_q1.next_q1, 100), 10) = 0 then
                        update linked_circuit set prev_q1 = cx_id_tgt where id = right_q1_id;
                    else
                        update linked_circuit set prev_q2 = cx_id_tgt where id = right_q1_id;
                    end if;

                    if mod(div(right_q2.next_q1, 100), 10) = 0 then
                        update linked_circuit set prev_q1 = cx_id_ctrl where id = right_q2_id;
                    else
                        update linked_circuit set prev_q2 = cx_id_ctrl where id = right_q2_id;
                    end if;

                    -- make sure to update the links for the cx
                    update linked_circuit set (switch, prev_q1, prev_q2, next_q1, next_q2, visited)
                                = (not cx.switch, left_q2.prev_q1, left_q1.prev_q1, right_q2.next_q1, right_q1.next_q1, 0) where id = cx.id;

                    delete from linked_circuit where id in (left_q1.id, left_q2.id, right_q1.id, right_q2.id);

                end if;
            end if;
        end loop;

        run_nr = run_nr - 1;

    end loop;
    commit;
end;$$;


