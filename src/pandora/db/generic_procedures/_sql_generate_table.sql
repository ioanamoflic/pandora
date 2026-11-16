CREATE OR REPLACE FUNCTION get_port_from_link(link bigint)
RETURNS bigint
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT mod(div(link, 100), 10);
$$;

CREATE OR REPLACE FUNCTION get_type_from_link(link bigint)
RETURNS smallint
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT mod(link, 100);
$$;

CREATE OR REPLACE FUNCTION get_id_from_link(link bigint)
RETURNS bigint
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT div(link, 1000);
$$;

CREATE OR REPLACE FUNCTION create_link(id bigint, port int, type smallint)
RETURNS bigint
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT id * 1000 + port * 100 + type;
$$;

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
    label   text,
    cl_ctrl boolean,
    meas_key smallint
) WITH (FILLFACTOR = 100);

-- For equivalence benchamrk
CREATE INDEX linked_circuit_type_idx on linked_circuit(type);

CREATE INDEX linked_circuit_next_ids_equal_idx on linked_circuit(type, (get_type_from_link(next_q1)))
where get_id_from_link(next_q1) = get_id_from_link(next_q2);
-- For equivalence benchamrk

CREATE TABLE IF NOT EXISTS gate_types (
    id smallint unique not null,
    name text unique not null
);

INSERT INTO gate_types (id, name) VALUES
(0, 'in'),           -- Input node (wire entry point)
(1, 'out'),          -- Output node (wire exit point)
(2, 'rx'),           -- Rotation around X axis by angle param
(3, 'ry'),           -- Rotation around Y axis by angle param
(4, 'rz'),           -- Rotation around Z axis by angle param
(5, 'xpow'),         -- X gate raised to the power param (XPowGate)
(6, 'ypow'),         -- Y gate raised to the power param (YPowGate)
(7, 'zpow'),         -- Z gate raised to the power param (ZPowGate)
(8, 'h'),            -- Hadamard gate
(9, 'paulix'),       -- Pauli X gate (bit-flip / NOT gate)
(10, 'pauliy'),      -- Pauli Y gate
(11, 'pauliz'),      -- Pauli Z gate (phase-flip)
(12, 'globalphase'), -- Global phase gate (unobservable scalar phase)
(13, 'reset'),       -- Reset qubit to |0⟩
(14, 'meas'),        -- Measurement gate (projects qubit to computational basis)
(15, 'cx'),          -- Controlled-X gate (CNOT)
(16, 'cz'),          -- Controlled-Z gate
(17, 'czpow'),       -- Controlled-Z gate raised to the power param
(18, 'cxpow'),       -- Controlled-X gate raised to the power param
(19, 'xxpow'),       -- XX interaction gate raised to the power param (Ising XX)
(20, 'zzpow'),       -- ZZ interaction gate raised to the power param (Ising ZZ)
(21, 'toffoli'),     -- Toffoli gate (doubly controlled X / CCX)
(22, 'and'),         -- AND gate (Toffoli with |0⟩ ancilla, uncompute-aware)
(23, 'ccx'),         -- Doubly controlled X gate (alias for Toffoli)
(24, 'cswap'),       -- Controlled-SWAP gate (Fredkin gate)
(25, 'globalin'),    -- Global input node (multi-qubit circuit entry)
(26, 'globalout'),   -- Global output node (multi-qubit circuit exit)
(27, 's'),           -- S gate (phase gate, sqrt(Z), π/2 rotation around Z)
(28, 'sdag'),        -- S† gate (inverse S, -π/2 rotation around Z)
(29, 't'),           -- T gate (π/8 gate, sqrt(S), π/4 rotation around Z)
(30, 'tdag'),        -- T† gate (inverse T, -π/4 rotation around Z)
(31, 'swap'),        -- SWAP gate (exchanges states of two qubits)
(32, 'zspider'),     -- Z spider
(33, 'xspider'),     -- X spider
(34, 'edge'),        -- Edge (for ZX diagrams, connects vertices)
(35, 'hbox');        -- H-box (generalized Hadamard vertex in ZX diagrams)

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

create table if not exists public.zx_rewrite_runs
(
    id bigserial primary key,
    procedure_name text not null,
    started_at timestamptz not null,
    execution_count bigint not null,
    elapsed_seconds double precision not null
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


create table IF NOT EXISTS public.layered_lscom
(
    id        bigserial primary key, 
    control_q bigint,
    target_q  bigint,
    type      smallint,
    param     real,
    layer     bigint
);


-- === ZX ===
CREATE OR REPLACE FUNCTION zx_phase_is_zero(p double precision)
RETURNS boolean
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT p = 0::double precision;
$$;

CREATE OR REPLACE FUNCTION zx_phase_is_pauli(p double precision)
RETURNS boolean
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT p IN (0::double precision, 1::double precision);
$$;

CREATE OR REPLACE FUNCTION zx_phase_is_clifford(p double precision)
RETURNS boolean
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT p IN (0::double precision, 0.5::double precision, 1::double precision, 1.5::double precision);
$$;

CREATE OR REPLACE FUNCTION zx_phase_is_proper_clifford(p double precision)
RETURNS boolean
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT p IN (0.5::double precision, 1.5::double precision);
$$;

create table zx_vertex (
    id bigserial primary key,
    type smallint not null,
    qubit bigint not null,
    row bigint not null,
    param double precision not null default 0 -- used as a pi multiplier
) WITH (FILLFACTOR = 50);

CREATE INDEX zx_vertex_type ON zx_vertex (type);
CREATE INDEX zx_vertex_zero_phase ON zx_vertex ((zx_phase_is_zero(param)));
CREATE INDEX zx_vertex_pauli ON zx_vertex ((zx_phase_is_pauli(param)));
CREATE INDEX zx_vertex_clifford ON zx_vertex ((zx_phase_is_clifford(param)));
CREATE INDEX zx_vertex_proper_clifford ON zx_vertex ((zx_phase_is_proper_clifford(param)));

-- Edges are stored with the smaller id as source. Use zx_check_edge_order to get the correct order for an edge
create table zx_edge (
    id bigserial primary key,
    type smallint not null,
    -- Encoded ZX vertex references: create_link(zx_vertex.id, 0, zx_vertex.type).
    -- Decode with get_id_from_link(ref) for the vertex id and get_type_from_link(ref)
    -- for the vertex type.
    source bigint not null,
    target bigint not null
);

CREATE UNIQUE INDEX zx_edge_pair_unique ON zx_edge (
    get_id_from_link(source),
    get_id_from_link(target)
);
CREATE INDEX zx_edge_target_id ON zx_edge (get_id_from_link(target));

-- Vertex types
CREATE OR REPLACE FUNCTION zx_const_input_type()      RETURNS smallint LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT 0::smallint  $$;
CREATE OR REPLACE FUNCTION zx_const_output_type()     RETURNS smallint LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT 1::smallint  $$;
CREATE OR REPLACE FUNCTION zx_const_z_spider()        RETURNS smallint LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT 32::smallint $$;
CREATE OR REPLACE FUNCTION zx_const_x_spider()        RETURNS smallint LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT 33::smallint $$;

-- Edge types
CREATE OR REPLACE FUNCTION zx_const_regular_edge()    RETURNS smallint LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT 0::smallint  $$;
CREATE OR REPLACE FUNCTION zx_const_hadamard_edge()   RETURNS smallint LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT 1::smallint  $$;


-- === belief-propagation ===

create table zx_bp_check_value (
    vertex_id bigint primary key references zx_vertex(id) on delete cascade,
    value     double precision not null
);
