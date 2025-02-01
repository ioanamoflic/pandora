To run the widgetization scripts and benchmarks you need to run `benchmark.py`.

The script takes the following parameters:
* `build` - builds the edge list of the circuit stored in a given table by topologically traversing it. The egde_list is
  stored into the `edge_list` table. 
* `uf` - is running the union-find-widgetization starting from the pre-compiled `edge_list` Pandora table.

In order to run `build` one needs a running PostgresSQL server in order to generate the corresponding decomposition into Pandora. 
The entire output of the processing is cached into the `edge_list` table.

