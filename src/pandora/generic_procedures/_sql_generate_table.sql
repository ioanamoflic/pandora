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

-- table only used for testing purposes
create table IF NOT EXISTS public.linked_circuit_test
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
    meas_key smallint,
    qubit_name varchar(50)
);

create table IF NOT EXISTS public.benchmark_results
(
    id      int primary key,
    pyliqtr_time float,
    pyliqtr_count int,
    decomp_time float,
    pandora_time float,
    pandora_count bigint,
    widgetisation_time float,
    widget_count int,
    extraction_time float
);

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


create table IF NOT EXISTS public.layered_cliff_t
(
    id        bigserial primary key, 
    control_q bigint,
    target_q  bigint,
    type      smallint,
    param     real,
    layer     bigint
);

create table IF NOT EXISTS public.minetest
(
    id        bigserial primary key unique,
    json      text
);