# Pandora HH-CX-HH Template Rewrite Benchmark

This script benchmarks Pandora’s stored-procedure rewrite rule for replacing `HH-CX-HH` templates with a reversed `CX`.

It generates random circuits containing `HH-CX-HH` patterns, stores them in Pandora, runs the rewrite procedure, checks correctness, and records rewrite runtime to CSV.
The rewrite rule applied here is 

```
───H───@───H───       ───X───
       │        ->       │
───H───X───H───       ───@───
```
---

## Requirements

Make sure you have:

- the apptainer setup from README.md
- a PostgreSQL config file (```default_config.json``` used here as an example)

---

## Running the Benchmark of for Pandora

```NPROCS``` gives the number of parallel optimiser workers:

* ```NPROCS > 0``` -  parallel rewrite,
* ```NPROCS = 0``` - sequential rewrite used for comparison with Qiskit and TKET.

### What the script does

For each sample percentage ```[0.1, 1, 10]``` the script:

1. Generates a random circuit with some flipped HH-CX-HH templates
2. Stores the circuit in Pandora
3. Runs either:
    * parallel ```linked_hhcxhh_to_cx```
    * sequential ```linked_hhcxhh_to_cx_seq```
4. Measures rewrite time

## Command

### For Pandora
```bash
bash run_apptainer.sh benchmarking/benchmark_pandora.py default_config.json <NPROCS>
```

### For Qiskit
```bash
bash run_apptainer_no_posgtres.sh benchmarking/benchmark_qiskit.py
```

### For TKET
```bash
bash run_apptainer_no_posgtres.sh benchmarking/benchmark_tket.py
```

### Plot
Too see the speed benchmark results summarised, you can run ```fig_speed()``` from ```benchmarking/plot_figs.py```:

```bash
bash run_apptainer_no_postgres.sh benchmarking/plot_figs.py
```