create table IF NOT EXISTS public.linked_circuit
(
    id      bigserial primary key,
    prev_q1 bigint,
    prev_q2 bigint,
    prev_q3 bigint,
    type    smallint,
    param   real,
    global_shift real,
    switch  boolean,
    next_q1 bigint,
    next_q2 bigint,
    next_q3 bigint,
    visited boolean,
    label   char,
    cl_ctrl boolean,
    meas_key smallint
);

-- create index IF NOT EXISTS btree_id
--     on public.linked_circuit (id);
--
-- create index IF NOT EXISTS btree_prev_q1
--     on public.linked_circuit (prev_q1);
--
-- create index IF NOT EXISTS btree_prev_q2
--     on public.linked_circuit (prev_q2);
--
-- create index IF NOT EXISTS btree_prev_q3
--     on public.linked_circuit (prev_q3);
--
-- create index IF NOT EXISTS btree_next_q1
--     on public.linked_circuit (next_q1);
--
-- create index IF NOT EXISTS btree_next_q2
--     on public.linked_circuit (next_q2);
--
-- create index IF NOT EXISTS btree_next_q3
--     on public.linked_circuit (next_q3);

create extension IF NOT EXISTS tsm_system_rows;

create table if not exists public.stop_condition
(
    stop boolean default false
);

create table if not exists public.edge_list
(
    source bigint,
    target bigint
);
