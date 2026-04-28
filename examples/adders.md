# Running the Pandora Adder Optimisation Benchmark

This script builds reversible adder circuits, stores them in Pandora’s PostgreSQL database, runs Pandora optimisation rules, and writes optimisation statistics to CSV.

## Requirements

You need:

- the apptainer setup from README.md
- a PostgreSQL config file (```default_config.json``` used here as an example)
- adder benchmark files are found under:

```text
benchmarking/adders/Adder16.txt
benchmarking/adders/Adder32.txt
...
benchmarking/adders/Adder2048.txt
```

## Run
It is recommended to run this benchmark using apptainer (see instructions in project readme):

```bash
bash run_apptainer.sh benchmarking/benchmark_adders.py default_config.json
```

For each adder size in ```[16, 32, 64, 128, 256, 512, 1024, 2048]```, the script:

1. loads the corresponding adder file 
2. converts it into a Qiskit circuit
3. decomposes all Toffoli gates into Clifford+T gates
4. stores the circuit in Pandora
5. runs optimisation rules with a timeout of 30 seconds
6. logs optimisation statistics
7. writes a CSV file for that adder size

## Important parameters
These mean each optimiser procedure is allowed to run for up to 30 seconds, with a very large pass limit.

```
timeout = 30
pass_count = int(1e7)
```

## Plot

Too see the optimisation results summarised, you can run ```fig_adders()``` and ```fig_adder_reduction()``` from ```benchmarking/plot_figs.py```:

```bash
bash run_apptainer_no_postgres.sh benchmarking/plot_figs.py
```