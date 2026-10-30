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
bash run_apptainer_toubkal.sh main.py rsa --n 64 --nproc 1 --container_id 0
```

Replace the storage path with your actual scratch directory. The launcher prefers
`apptainer` and falls back to `singularity`. It starts one Slurm task on one node;
allocate enough CPUs for `--nproc`. It accepts `PANDORA_IMAGE` and `--config` and
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
bash run_apptainer_lumi.sh main.py rsa --n 64 --nproc 1 --container_id 0
```

Replace the scratch path with a directory you can write to. The launcher also
accepts `$SCRATCH` as the default storage root and `PANDORA_IMAGE` as an alternate
image path. Match `--nproc` to the CPUs allocated to your job.

When run outside an allocation, the launcher requests one with `salloc`, waits
for resources, and runs the command automatically. It defaults to the account
`project_462000921` used in `run_lumi.sh`, the `small` partition, 8G memory,
30 minutes, and one CPU per `--nproc` worker. Set `PANDORA_ACCOUNT` (or
`SLURM_ACCOUNT`) for your own project. Other overrides are `PANDORA_PARTITION`,
`PANDORA_CPUS`, `PANDORA_MEM`, and `PANDORA_TIME`. Without a storage override,
automatic allocation uses `/scratch/<account>/$USER/pandora-db`. Existing Slurm
allocations are reused, and their resources are not changed.

For custom local database settings, pass `main.py --config config.json rsa ...`.
The launcher reads the JSON port, user, and database, initializes that user and
database, and starts PostgreSQL on localhost. It uses trust authentication for
local connections; use this launcher for trusted cluster workloads. Each run
creates a fresh database directory, retains it and the PostgreSQL log in the
printed run directory, and stops PostgreSQL on exit. Existing databases are not
automatically reused.
