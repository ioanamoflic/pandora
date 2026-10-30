# Build the Pandora Apptainer image

From the repository root, with Apptainer available:

```bash
bash apptainer/apptainer_util.sh base
bash apptainer/apptainer_util.sh build
```
The helper also works from inside `apptainer/`. It changes into that directory
so the relative base-image path and `%files` source (`..`, the repository)
resolve consistently. Docker is not needed. The resulting image is
`apptainer/images/pandora.sif`.

The build needs network access to download the base image and Python dependencies.
Use a machine or node where your cluster permits container builds.

## Running on Toubkal

Load the cluster's Apptainer module if needed, and build the image using the
commands above. Inside an `sbatch` job or `salloc` allocation, run:

```bash
export PANDORA_DATA_ROOT=/path/to/your/writable/scratch/pandora-db
bash run_apptainer_toubkal.sh main.py rsa --n 64 --nproc 1 --container_id 0
```

Replace the storage path with your actual scratch directory. The launcher prefers
`apptainer` and falls back to `singularity`. It starts one Slurm task on one node;
allocate enough CPUs for `--nproc`. It accepts `PANDORA_IMAGE` and `--config` and
retains the database and logs in a unique directory, as described below for LUMI.
It requires Slurm's `srun`; cluster-specific partition/account/resource options
belong in your job submission or allocation command.

## Running on LUMI

LUMI uses `singularity`. Build the image using LUMI's PRoot procedure or transfer
a Linux x86-64 image built elsewhere. Inside a single-node Slurm allocation,
run from the repository root:

```bash
export PANDORA_DATA_ROOT=/scratch/project_YOUR_PROJECT/$USER/pandora-db
bash run_apptainer_lumi.sh main.py rsa --n 64 --nproc 1 --container_id 0
```

Replace the scratch path with a directory you can write to. The launcher also
accepts `$SCRATCH` as the default storage root and `PANDORA_IMAGE` as an alternate
image path. Match `--nproc` to the CPUs allocated to your job.

For custom local database settings, pass `main.py --config config.json rsa ...`.
The launcher reads the JSON port, user, and database, initializes that user and
database, and starts PostgreSQL on localhost. It uses trust authentication for
local connections; use this launcher for trusted cluster workloads. Each run
creates a fresh database directory, retains it and the PostgreSQL log in the
printed run directory, and stops PostgreSQL on exit. Existing databases are not
automatically reused.
