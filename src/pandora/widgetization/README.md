To run the widgetization scripts and benchmarks you need to run `benchmark.py`.

The script takes the following parameters:
* `plot3d` - plots the results of the union find stored in `widget_bench.csv`
* `build` - is retrieving from the PostgreSQL a list of edges and stores them in the `edges.txt`
* `union` - is running the union-find-widgetization starting from the `edges.txt`

In order to run `build` one needs a running PostgresSQL server in order to generate into Pandora
the corresponding decomposition. The entire output of the processing is cached into `edges.txt`.

