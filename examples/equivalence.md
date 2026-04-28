# Pandora vs MQT Equivalence Benchmark

This script benchmarks quantum circuit equivalence checking using:

- **Pandora**
- **MQT QCEC ZX checker**
- **MQT QCEC DD checker**

It generates random CNOT circuits, constructs equivalent or non-equivalent pairs, runs verification, and records performance results.

---

## Requirements

Make sure you have:

- the apptainer setup from README.md
- a PostgreSQL config file (```default_config.json``` used here as an example)

---

## Running the Benchmark

### Parameters

```IS_EQUIV``` controls whether the generated circuits are equivalent:
* ```0``` - equivalent circuits (second circuit is identical copy)
* ```1``` - non-equivalent circuits (second circuit is modified by removing one random gate)

```BACKEND``` selects the verification engine:
* ```pandora``` - rewrite-based verification
* ```zx``` - MQT ZX checker
* ```dd``` - MQT decision diagram checker

```bash
bash run_apptainer.sh benchmarking/benchmark_mqt.py default_config.json <IS_EQUIV> <BACKEND>
```
### What the Script Does

For each run:
1. Generate a random CNOT circuit
2. Save it as QASM
3. Create a second circuit:
    * identical copy (if equivalent case)
    * modified version (if non-equivalent case)
4. Run selected backend
5. Record:
    * equivalence result
    * runtime

### Plot
The results are summarised in ```<backend>_<is_equiv>_verification.csv```.
Too see the verification results summarised, you can run ```fig_verification()``` from ```benchmarking/plot_figs.py```:

```bash
bash run_apptainer_no_postgres.sh benchmarking/plot_figs.py
```