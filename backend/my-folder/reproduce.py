import argparse
import os
import tempfile

import config
from common import write_json
from generate_data import generate


def run(scale, seed, report_path, quiet=False):
    with tempfile.TemporaryDirectory() as tmp:
        a = generate(scale, seed, os.path.join(tmp, "run_a"), quiet=True)
        b = generate(scale, seed, os.path.join(tmp, "run_b"), quiet=True)
        c = generate(scale, seed + 1, os.path.join(tmp, "run_other_seed"), quiet=True)
    files_a = {f["path"]: f for f in a["files"]}
    files_b = {f["path"]: f for f in b["files"]}
    files_c = {f["path"]: f for f in c["files"]}
    comparison = []
    for path in sorted(files_a):
        fa, fb = files_a[path], files_b.get(path, {})
        comparison.append({"file": path, "rows_run_a": fa["rows"], "rows_run_b": fb.get("rows"),
                           "sha256_run_a": fa["sha256"], "sha256_run_b": fb.get("sha256"),
                           "identical": fa["sha256"] == fb.get("sha256")})
    identical = all(x["identical"] for x in comparison) and set(files_a) == set(files_b)
    differs = any(files_a[p]["sha256"] != files_c[p]["sha256"] for p in files_a if p in files_c)
    report = {"scale": scale, "seed": seed, "runs": 2, "identical": identical,
              "different_seed_changes_data": differs, "files": comparison}
    write_json(report_path, report)
    if not quiet:
        print(f"[reproduce] 2 runs with seed {seed}: identical={identical}; seed {seed + 1} differs={differs}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="starter")
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = args.out or os.path.join("output", args.scale)
    run(args.scale, args.seed, os.path.join(root, "reproducibility_report.json"))
