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

The recipe uses `postgres:17-bookworm` to provide Python 3.11. Do not substitute
`postgres:latest`: its Python 3.13 is incompatible with NumPy 1.26.x selected by
the RSA dependency stack. NumPy is installed from a binary wheel.

## Running on Toubkal

Load the cluster's Apptainer module if needed, and build the image using the
commands above. Inside an `sbatch` job or `salloc` allocation, run:

```bash
export PANDORA_DATA_ROOT=/path/to/your/writable/scratch/pandora-db
bash run_apptainer_toubkal.sh main.py rsa --n 64 --nodes 3 --nproc 4
```

Replace the storage path with your actual scratch directory. The launcher prefers
`apptainer` and falls back to `singularity`. It starts one Slurm task per requested
node; allocate `--nodes` nodes with at least `--nproc` CPUs per task. It accepts `PANDORA_IMAGE` and `--config` and
retains the database and logs in a unique directory, as described below for LUMI.
It requires Slurm's `srun`; cluster-specific partition/account/resource options
belong in your job submission or allocation command.

## Running on LUMI

For PRoot builds, keep `--no-install-recommends` in the recipe's `apt-get install`
command. Otherwise Git pulls in `openssh-client`, whose configuration can fail
while creating the `_ssh` group (`failure while writing changes to /etc/group`).
Rebuild from the PostgreSQL 17 Bookworm base image after updating the recipe:

```bash
module load CrayEnv
module load PRoot
cd apptainer
mkdir -p images
singularity pull images/postgres:17-bookworm.sif docker://postgres:17-bookworm
singularity build images/pandora.sif project.apptainer
```

LUMI uses `singularity`. Build the image using LUMI's PRoot procedure or transfer
a Linux x86-64 image built elsewhere. Run from the repository root:

```bash
export PANDORA_DATA_ROOT=/scratch/project_YOUR_PROJECT/$USER/pandora-db
bash run_apptainer_lumi.sh main.py rsa --n 64 --nodes 3 --nproc 4
```

Replace the scratch path with a directory you can write to. The launcher also
accepts `$SCRATCH` as the default storage root and `PANDORA_IMAGE` as an alternate
image path. Match `--nproc` to the CPUs allocated to your job.

When run outside an allocation, the launcher submits itself with `sbatch` and returns a job ID.
Output and errors go to `container_outputs/pandora-<jobid>.out` and `.err`;
set `PANDORA_LOG_DIR` to change the log directory. It defaults to the account
`project_462001731`, 8G memory, 30 minutes, and `--nproc` CPUs per node.
It selects `small` for up to four nodes and `standard` above four nodes;
`standard` charges for full nodes. Memory is also per node. Set `PANDORA_ACCOUNT` (or
`SLURM_ACCOUNT`) for your own project. Other overrides are `PANDORA_PARTITION`,
`PANDORA_CPUS`, `PANDORA_MEM`, and `PANDORA_TIME`. Without a storage override,
automatic submission uses `/scratch/<account>/$USER/pandora-db`. Existing Slurm
allocations are reused, and their resources are not changed.

`--nodes` defaults to 1 and replaces the former `--container_id` option. Slurm
starts exactly one container on each requested node and assigns IDs `0` through
`--nodes - 1`. Each container decomposes a different contiguous chunk of the
high-level circuit, split further among its `--nproc` workers. For example,
`--nodes 3 --nproc 4` launches 12 decomposition workers in total. Override the
partition with `PANDORA_PARTITION` if needed; see
[LUMI's partition limits](https://docs.lumi-supercomputer.eu/runjobs/scheduled-jobs/partitions/).

Results stay in separate databases under the printed run directory's `node-0/`,
`node-1/`, etc.; each contains `pgdata/` and `postgres.log`. They are not merged
into a single database. A worker failure makes its node and the Slurm job fail.
Copy the updated source files and all scripts in `apptainer/` to the cluster;
the launcher binds the repository into the image, so these code changes do not
require rebuilding the image.

For custom local database settings, pass `main.py --config config.json rsa ...`.
The launcher reads the JSON port, user, and database, initializes that user and
database, and starts PostgreSQL on localhost. Without an explicit port, it selects
an available port on each node and passes it to Pandora via `PGPORT`. It uses trust authentication for
local connections; use this launcher for trusted cluster workloads. Each run
creates a fresh database directory, retains it and the PostgreSQL log in the
printed run directory, and stops PostgreSQL on exit. Existing databases are not
automatically reused.
