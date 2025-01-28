# Pandora: Ultra-Large-Scale Quantum Circuit Design Automation

**Pandora** is an open-source tool for compiling, analyzing and optimizing quantum circuits through template rewrite rules. The tool can easily handle quantum circuits with tens of millions of gates, and can operate in a multi-threaded manner offering almost linear speed-ups. Pandora can apply thousands of complex circuit rewrites per second at random circuit locations.
* Faster and more insightful analysis of quantum circuits
* Faster compilation for practical, fault-tolerant QC
* Faster and multi-threaded optimization for practical, fault-tolerant QC

Preliminary results for illustrating the speed-up: a) single threaded performance vs Tket for cancelling pairs of Hadamard gates (horizontal axis); b) multi-threaded speed-up (vertical) when cancelling Hadamard gates using specified number of cores (horizontal); c) multi-threaded speed-up (vertical) when reverting the direction of CNOT gates using specified number of cores (horizontal).
![pandora_res.png](pandora_res.png)

**Pandora** is integrated with <a href="https://github.com/quantumlib/Qualtran" target=_blank>Google Qualtran</a>.

A tutorial including setup instructions is <a href="https://colab.research.google.com/drive/1K7cEqRoXRAOOhEz4EmfSPtBUssaXPW-v?usp=sharing" target="_blank">here</a>

**This research was performed in part with funding from the Defense Advanced Research Projects Agency [under the Quantum Benchmarking
(QB) program under award no. HR00112230006 and HR001121S0026 contracts].**


## Docker Setup
Requires `docker`, `docker-compose` and `docker-buildx`.

The image may be built and run using:
```bash
    docker compose up --build    
```

```bash
    sudo dpkg -i containernetworking-plugins_1.1.1+ds1-3build1_amd64.deb
```

The resulting docker image will host the database on port 5432 on the docker image. The default password is `example` and can be changed in compose.yml. 

## First Steps 

TODO: More documentation
* Install PostgreSQL and get a server running. For example, on MacOS you can use [this](https://www.atlassian.com/data/sql/how-to-start-a-postgresql-server-on-mac-os-x)
* `python main.py adder 8` for building an 8-bit adder

## Widgetization
This is an example of a widgetised Fermi-Hubbard instance (N=2) decomposed into Clifford+T with around 58K gates.
Each frame is a visualisation of the widgets with d3 (each node is a gate, the color identifies the widget) for different parameters.

![fh2.gif](fh2.gif)

<a href="./vis/index.html" target=_blank>Example</a>
