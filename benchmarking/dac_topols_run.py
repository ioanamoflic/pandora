"""TopoLS comparison, step 2: run TopoLS on every QASM in <work dir>/benchmark.

    python benchmarking/dac_topols_run.py <work dir> <seed> [--python <TopoLS venv python>] [--topols <TopoLS checkout>]

Runs TopoLS docs/prog.py (Python engine, the settings of the TopoLS README) on
each input in parallel, one working directory per run, and writes
<work dir>/topols_r<seed>.json with the space-time volume and layout size.
"""
import json, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

D = Path(sys.argv[1]); SEED = sys.argv[2] if len(sys.argv) > 2 else "0"
def _opt(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default
ROOT = Path(__file__).resolve().parent.parent
PY = _opt("--python", str(ROOT / ".venv_claude/bin/python"))
PROG = str(Path(_opt("--topols", str(ROOT / "TopoLS"))) / "docs/prog.py")
ARGS = ["-b", "20", "-zx", "1", "-dir", "1", "-l", "4", "-r", SEED, "-s", "2", "-t", "2", "-i", "1000",
        "-csv", "result", "-sp", "0"]

def run(q):
    name = q.stem
    work = D / f"work_r{SEED}" / name
    (work / "benchmark").mkdir(parents=True, exist_ok=True)
    shutil.copy(q, work / "benchmark" / q.name)
    try:
        p = subprocess.run([PY, PROG, "-f", name, *ARGS], cwd=work, capture_output=True, text=True, timeout=1800)
        out = p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return name, {"error": "timeout"}
    m = {k: re.search(rf"{k}: ([0-9.]+)", out) for k in ("Space-time volume", "Time", "Space", "Compilation time")}
    if not m["Space-time volume"]:
        return name, {"error": out[-300:]}
    dims = re.search(r"x_length: ([0-9.]+) y_length: ([0-9.]+) z_length: ([0-9.]+)", out)
    return name, {"volume": float(m["Space-time volume"].group(1)), "time": float(m["Time"].group(1)),
                  "space": float(m["Space"].group(1)), "compile_s": float(m["Compilation time"].group(1)),
                  "dims": [float(x) for x in dims.groups()] if dims else None}

qs = sorted((D / "benchmark").glob("*.qasm"))
with ThreadPoolExecutor(max_workers=36) as ex:
    results = dict(ex.map(run, qs))
(D / f"topols_r{SEED}.json").write_text(json.dumps(results, indent=1))
print(f"{len(results)} runs, {sum('error' in r for r in results.values())} errors")
