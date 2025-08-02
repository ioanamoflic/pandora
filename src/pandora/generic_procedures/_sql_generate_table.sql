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
--     visited boolean,
    visited int default -1 ,
    label   char,
    cl_ctrl boolean,
    meas_key smallint
) WITH (FILLFACTOR = 50);

CREATE INDEX ON linked_circuit (type);
-- CREATE INDEX idx_linked_circuit_id_mod_2 ON linked_circuit (id) WHERE id % 2 = 1;

CREATE INDEX idx_linked_circuit_prev1_mod_100 ON linked_circuit (next_q1, next_q2) WHERE div(next_q1, 1000) = div(next_q2, 1000);
-- CREATE INDEX idx_linked_circuit_prev2_mod_100 ON linked_circuit (prev_q1) WHERE prev_q1 % 100 = 8;
-- CREATE INDEX idx_linked_circuit_prev2_mod_100 ON linked_circuit (prev_q2) WHERE prev_q2 % 100 = 8;
-- CREATE INDEX idx_linked_circuit_next1_mod_100 ON linked_circuit (next_q1) WHERE next_q1 % 100 = 8;
-- CREATE INDEX idx_linked_circuit_next2_mod_100 ON linked_circuit (next_q2) WHERE next_q2 % 100 = 8;


create table IF NOT EXISTS public.optimization_results
(
    id int,
    logger_id int,
    total_count int,
    t_count int,
    s_count int,
    h_count int,
    cx_count int,
    x_count int
);

create table IF NOT EXISTS public.batched_circuit
(
    id int,
    prev_q1 int,
    prev_q2 int,
    prev_q3 int,
    type    smallint,
    param   numeric,
    global_shift real,
    switch  boolean,
    next_q1 int,
    next_q2 int,
    next_q3 int,
    visited boolean,
    label   serial,
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

create table if not exists public.max_missed_rounds
(
    missed int default 0
);

create table if not exists public.rewrite_count
(
    proc_id int primary key,
    count int default 0
);

create table if not exists public.edge_list
(
    source bigint,
    target bigint
);

create table if not exists public.mem_cx
(
    id bigint primary key
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

