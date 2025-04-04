![Logo](pandoraos_logo_resized.png)

# Pandora: Ultra-Large-Scale Quantum Circuit Design Automation

## About
**Pandora** is an open-source tool for compiling, analyzing and optimizing quantum circuits through template rewrite rules. 
The tool can easily handle quantum circuits with hundreds of millions of gates, and can operate in a multi-threaded manner 
offering almost linear speed-ups. Pandora can apply thousands of complex circuit rewrites per second at random circuit locations.

Pandora is HPC friendly and can be used for:
* Faster and more insightful analysis of quantum circuits
* Faster compilation for practical, fault-tolerant QC
* Faster and multi-threaded optimization for practical, fault-tolerant QC
* Fast widgetisation. A widget is a partition of the circuit which obeys some architectural constraints.

Preliminary results for illustrating the speed-up (random circuit locations) of the optimisation: 
a) single threaded performance vs TKET for cancelling pairs of Hadamard gates (horizontal axis); 
b) multi-threaded speed-up (vertical) when cancelling Hadamard gates using specified number of cores (horizontal); 
c) multi-threaded speed-up (vertical) when reverting the direction of CNOT gates using specified number of cores (horizontal).

![pandora_res.png](pandora_res.png)

**Pandora** is integrated with <a href="https://github.com/quantumlib/Qualtran" target=_blank>Google Qualtran</a> and <a href="https://github.com/isi-usc-edu/pyLIQTR" target=_blank>pyLIQTR</a>.

## Apptainer Setup
Installation instructions can be found in the `README.md` of the `apptainer` folder. In a nutshell, you need to have
Apptainer installed on your computer, a Docker image of Postgres available locally, and then to follow the 
steps from the README. At the end you will see a `pandora.sif` file in the `apptainer\images` folder. This is the
Apptainer image that will be used by `run_apptainer.sh` (see following section).

## With Apptainer 
For running on HPC hardware, this is highly encouraged. Apptainer does not require sudo rights and is also light-weight and open-source.
Multiple Pandora containers can be started in parallel, each with its own `.json` config file (make sure that the port is different). 

* A PostgreSQL config file example is `default_config.json`.
* The database storage location can be configured in `run_apptainer.sh`. As a rule of thumb, each billion of Clifford+T 
gates in the Pandora format takes about 100GB of storage.
* A command example for starting the container and decomposing an N=10 Fermi-Hubbard instance is
```
bash run_apptainer.sh main.py default_config.json fh 10
```

## Without Apptainer
* Install PostgreSQL and get a server running. For example, on MacOS you can use [this tutorial](https://www.atlassian.com/data/sql/how-to-start-a-postgresql-server-on-mac-os-x).
* A PostgreSQL config file example is `default_config.json`. 
* `python main.py adder 8` for building and decomposing an 8-bit adder into Pandora.

## Widgetization
This is an example of a widgetised Fermi-Hubbard instance (N=2) decomposed into Clifford+T with around 58K gates.
Each frame is a visualisation of the widgets with d3 (each node is a gate, the color identifies the widget) for different parameters.

![fh2.gif](fh2.gif)

<a href="./vis/index.html" target=_blank>This is an example of a widgetised 2-bit adder.</a>

## Acknowledgements
**This research was performed in part with funding from the Defense Advanced Research Projects Agency [under the Quantum Benchmarking
(QB) program under award no. HR00112230006 and HR001121S0026 contracts].**
