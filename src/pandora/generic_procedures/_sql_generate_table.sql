create table IF NOT EXISTS public.linked_circuit
(
    id      bigserial primary key,
    prev_q1 bigint,
    prev_q2 bigint,
    prev_q3 bigint,
    type    smallint,
    param   real,
    global_shift real default 0,
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

CREATE INDEX idx_linked_circuit_prev1_mod_100 ON linked_circuit (next_q1, next_q2) WHERE div(next_q1, 1000) = div(next_q2, 1000);

CREATE TABLE IF NOT EXISTS gate_types (
    id smallint unique not null,
    name text unique not null
);

INSERT INTO gate_types (id, name) VALUES
(0, 'in'),
(1, 'out'),
(2, 'rx'),
(3, 'ry'),
(4, 'rz'),
(5, 'xpow'),
(6, 'ypow'),
(7, 'zpow'),
(8, 'h'),
(9, 'paulix'),
(10, 'pauliy'),
(11, 'pauliz'),
(12, 'globalphase'),
(13, 'reset'),
(14, 'meas'),
(15, 'cx'),
(16, 'cz'),
(17, 'czpow'),
(18, 'cxpow'),
(19, 'xxpow'),
(20, 'zzpow'),
(21, 'toffoli'),
(22, 'and'),
(23, 'ccx'),
(24, 'cswap'),
(25, 'globalin'),
(26, 'globalout'),
(27, 's'),
(28, 'sdag'),
(29, 't'),
(30, 'tdag'),
(31, 'swap');

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

