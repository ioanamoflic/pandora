# Shared host-side resource parsing for the LUMI and Toubkal launchers.
parse_cluster_resources() {
    NODES=1
    WORKERS=1
    local args=("$@") i
    for ((i=1; i<${#args[@]}; i++)); do
        case "${args[i]}" in
            --nodes) NODES="${args[i+1]:-}"; ((i+=1)) ;;
            --nodes=*) NODES="${args[i]#--nodes=}" ;;
            --nproc) WORKERS="${args[i+1]:-}"; ((i+=1)) ;;
            --nproc=*) WORKERS="${args[i]#--nproc=}" ;;
            --container_id|--container_id=*)
                echo "Use --nodes instead of --container_id; node IDs are assigned automatically." >&2
                return 2 ;;
        esac
    done
    if [[ ! "$NODES" =~ ^[1-9][0-9]*$ || ! "$WORKERS" =~ ^[1-9][0-9]*$ ]]; then
        echo "--nodes and --nproc must be positive integers." >&2
        return 2
    fi
    CPUS="${PANDORA_CPUS:-$WORKERS}"
    if [[ ! "$CPUS" =~ ^[1-9][0-9]*$ ]] || ((CPUS < WORKERS)); then
        echo "PANDORA_CPUS must be a positive integer at least as large as --nproc." >&2
        return 2
    fi
    if [[ -n ${SLURM_JOB_ID:-} ]]; then
        if [[ -n ${SLURM_JOB_NUM_NODES:-} ]] && ((SLURM_JOB_NUM_NODES < NODES)); then
            echo "Allocation has $SLURM_JOB_NUM_NODES nodes; --nodes requests $NODES." >&2
            return 2
        fi
        if [[ -n ${SLURM_CPUS_PER_TASK:-} ]] && ((SLURM_CPUS_PER_TASK < CPUS)); then
            echo "Allocation has $SLURM_CPUS_PER_TASK CPUs per task; $CPUS are required." >&2
            return 2
        fi
    fi
}

launch_cluster_nodes() {
    local runtime="$1"
    shift
    # One task per physical node; each task launches its own worker processes.
    # Use a shared script, because srun normally sends stdin only to task zero.
    srun --nodes="$NODES" --ntasks="$NODES" --ntasks-per-node=1 \
        --cpus-per-task="$CPUS" --kill-on-bad-exit=1 --input=none \
        bash "$REPO_DIR/apptainer/slurm_node.sh" \
        "$runtime" "$REPO_DIR" "$IMAGE" "$RUN_DIR" "$NODES" "$WORKERS" "$(id -un)" "$@"
}
