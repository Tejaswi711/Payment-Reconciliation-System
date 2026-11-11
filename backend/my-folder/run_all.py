import argparse
import os
import time
import config
import evaluate
import export_sql
import report
import reproduce
import reconcile
import schema
import validate
from generate_data import generate


def main():
    ap = argparse.ArgumentParser(description="Payment reconciliation pipeline")
    ap.add_argument("--scale", choices=list(config.SCALES), default="starter")
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--out", default=None, help="output folder (default output/<scale>)")
    ap.add_argument("--skip-repro", action="store_true", help="skip the double generation check")
    ap.add_argument("--skip-seed-sql", action="store_true", help="do not write the (large) seed.sql file")
    a = ap.parse_args()
    out = a.out or os.path.join("output", a.scale)
    start = time.time()

    schema.write_docs(".")
    print("[docs] docs/data_dictionary.md, sql/schema.sql")
    generate(a.scale, a.seed, out)
    reconcile.run(os.path.join(out, "data"), os.path.join(out, "recon"))
    v = validate.run(out, a.scale)
    e = evaluate.run(out)
    s = export_sql.run(out, write_seed_sql=not a.skip_seed_sql)
    r = None if a.skip_repro else reproduce.run(a.scale, a.seed, os.path.join(out, "reproducibility_report.json"))
    report.run(out)

    ok = v["overall"] == "PASS" and e["overall"] == "PASS" and s["fk_violations"] == 0 and (r is None or r["identical"])
    print(f"\nDONE in {time.time() - start:.1f}s -> {'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'}")
    print(f"Open {os.path.join(out, 'report.html')} in a browser.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
