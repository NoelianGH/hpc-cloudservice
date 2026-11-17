"""
Uji kebenaran job multi-tahap heat2d TANPA Docker/database:
  1. hasil terdistribusi (per blok + halo, tahap demi tahap) identik bit-per-bit dengan serial;
  2. kernel di worker, di koordinator, dan di job-template/run.py identik.

Jalankan dari root repo:  python3 tests/test_heat2d.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "head", "coordinator"))
try:
    import psycopg  # noqa: F401
except ImportError:  # jobs.py hanya butuh Jsonb saat menulis ke database
    pkg = types.ModuleType("psycopg"); sub = types.ModuleType("psycopg.types"); js = types.ModuleType("psycopg.types.json")
    js.Jsonb = lambda x: x
    sys.modules.update({"psycopg": pkg, "psycopg.types": sub, "psycopg.types.json": js})

import jobs  # noqa: E402

os.environ.setdefault("COORDINATOR_URL", "http://localhost:8000")
os.environ.setdefault("WORKER_TOKEN", "test")
spec_w = importlib.util.spec_from_file_location("worker", os.path.join(ROOT, "compute", "worker.py"))
worker = importlib.util.module_from_spec(spec_w)
spec_w.loader.exec_module(worker)


def distributed(spec):
    grid = jobs.heat_initial(spec["n"], spec["t_hot"], spec["t_cold"])
    for stage in range(spec["stages"]):
        results = [worker.heat2d(p) for p in jobs.heat_payloads(spec, grid, stage)]  # compute
        grid = jobs.heat_assemble(results)                                           # communicate
    return grid


def run_template(payload):
    out = subprocess.run([sys.executable, os.path.join(ROOT, "job-template", "run.py")],
                         input=json.dumps({"kind": "heat2d", "payload": payload}),
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


def main():
    cases = [dict(jobs.HEAT_DEFAULTS, n=40, blocks=4, stages=5, steps=6),
             dict(jobs.HEAT_DEFAULTS, n=33, blocks=5, stages=3, steps=7),   # blok tidak sama besar
             dict(jobs.HEAT_DEFAULTS, n=24, blocks=8, stages=4, steps=5)]   # halo > tinggi blok
    for spec in cases:
        d, s = distributed(spec), jobs.heat_serial(spec)
        ok = jobs.canonical_hash(d) == jobs.canonical_hash(s)
        print(f"n={spec['n']:>3} blok={spec['blocks']} tahap={spec['stages']} langkah={spec['steps']}: "
              f"terdistribusi == serial -> {ok}")
        assert ok
    p = jobs.heat_payloads(cases[0], jobs.heat_initial(40, 100.0, 0.0), 0)[1]
    assert worker.heat2d(p) == jobs.heat_step_block(p) == run_template(p)
    print("kernel worker == koordinator == job-template/run.py -> True")
    print("SEMUA UJI LULUS")


if __name__ == "__main__":
    main()
