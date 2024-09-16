create table IF NOT EXISTS public.linked_circuit_qubit
(
    id bigserial primary key,
    prev_q1 bigint,
    prev_q2 bigint,
    prev_q3 bigint,
    type    varchar(20),
    param   real,
    switch  boolean,
    next_q1 bigint,
    next_q2 bigint,
    next_q3 bigint,
    visited boolean,
    label varchar(20),
    cl_ctrl boolean,
    meas_key char,
    qub_1 int,
    qub_2 int,
    qub_3 int
);

create index IF NOT EXISTS btree_id
    on public.linked_circuit_qubit (id);

create index IF NOT EXISTS btree_prev_q1
    on public.linked_circuit_qubit (prev_q1);

create index IF NOT EXISTS btree_prev_q2
    on public.linked_circuit_qubit (prev_q2);

create index IF NOT EXISTS btree_prev_q3
    on public.linked_circuit_qubit (prev_q3);

create index IF NOT EXISTS btree_next_q1
    on public.linked_circuit_qubit (next_q1);

create index IF NOT EXISTS btree_next_q2
    on public.linked_circuit_qubit (next_q2);

create index IF NOT EXISTS btree_next_q3
    on public.linked_circuit_qubit (next_q3);

create extension IF NOT EXISTS tsm_system_rows;

create table if not exists public.stop_condition
(
    stop boolean default false
)