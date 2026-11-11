import argparse
import csv
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from decimal import Decimal

import config
from common import money, read_csv, sha256_file, write_json
import reconcile

MATCHED = ("MATCHED", "MATCHED_WITH_TOLERANCE")
NEEDS_EXCEPTION = ("PARTIAL", "UNMATCHED", "DUPLICATE")


def check(name, passed, detail):
    return {"criterion": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def score_ground_truth(gt, exceptions, matches, dedup):
    exc_keys = {(e["exception_type"], e["entity_id"]) for e in exceptions}
    dedup_ids = {d["ingest_id"] for d in dedup}
    batch_status = {m["batch_id"]: m["match_status"] for m in matches
                    if m["match_level"] == "BATCH_TO_BANK" and m["batch_id"] and m["match_status"] != "DUPLICATE"}
    event_status = {m["event_id"]: m["match_status"] for m in matches
                    if m["match_level"] == "EVENT_TO_SETTLEMENT" and m["match_status"] != "DUPLICATE"}

    per_issue = defaultdict(lambda: {"category": "", "expected": 0, "handled": 0, "missed": []})
    expected_exc = set()
    for g in gt:
        exp, eid = g["expected_decision"], g["entity_id"]
        if exp.startswith("EXCEPTION:"):
            key = (exp.split(":", 1)[1], eid)
            expected_exc.add(key)
            ok = key in exc_keys
        elif exp == "DEDUPLICATED":
            ok = eid in dedup_ids
        elif exp == "MATCHED_WITH_TOLERANCE":
            ok = batch_status.get(eid) == "MATCHED_WITH_TOLERANCE"
        elif exp == "MATCHED" and g["entity_type"] == "ProcessorEvent":
            ok = event_status.get(eid) == "MATCHED"
        else:
            ok = batch_status.get(eid) in MATCHED
        s = per_issue[g["issue_type"]]
        s["category"] = g["category"]
        s["expected"] += 1
        s["handled"] += ok
        if not ok:
            s["missed"].append(eid)
    for s in per_issue.values():
        s["recall"] = round(s["handled"] / s["expected"], 4)
        s["missed"] = s["missed"][:5]

    per_type = defaultdict(lambda: {"raised": 0, "true_positive": 0})
    false_positives = []
    for e in exceptions:
        key = (e["exception_type"], e["entity_id"])
        per_type[e["exception_type"]]["raised"] += 1
        if key in expected_exc:
            per_type[e["exception_type"]]["true_positive"] += 1
        else:
            false_positives.append(e["exception_id"])
    for v in per_type.values():
        v["precision"] = round(v["true_positive"] / v["raised"], 4)

    anomalies = [g for g in gt if g["category"] == "ANOMALY"]
    handled = sum(per_issue[i]["handled"] for i in {g["issue_type"] for g in anomalies})
    tp = len(exceptions) - len(false_positives)
    exc_expected = len(expected_exc)
    precision = tp / len(exceptions) if exceptions else 1.0
    recall = tp / exc_expected if exc_expected else 1.0
    return {
        "anomaly_cases": len(anomalies), "anomaly_cases_handled": handled,
        "anomaly_recall": round(handled / len(anomalies), 4) if anomalies else None,
        "scenario_cases": len(gt) - len(anomalies),
        "scenario_accuracy": round(sum(s["handled"] for s in per_issue.values() if s["category"] == "SCENARIO")
                                   / max(1, len(gt) - len(anomalies)), 4),
        "exception_precision": round(precision, 4), "exception_recall": round(recall, 4),
        "exception_f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0,
        "false_positive_exceptions": false_positives[:10],
        "by_issue_type": dict(sorted(per_issue.items())),
        "by_exception_type": dict(sorted(per_type.items())),
    }


def acceptance(scale_dir, data, out):
    matches, exceptions, resolutions = out["reconciliation_matches"], out["exceptions"], out["resolutions"]
    results = []

    bad = [m["match_id"] for m in matches if m["match_status"] in MATCHED
           and abs(Decimal(m["difference"] or 0)) > Decimal(m["tolerance"] or 0)]
    n = sum(m["match_status"] in MATCHED for m in matches)
    results.append(check("Matched amounts reconcile under configured tolerance", not bad,
                         f"{n:,} matched decisions, {len(bad)} outside tolerance"))

    with_exc = {e["match_id"] for e in exceptions if e["match_id"]}
    missing_exc = [m["match_id"] for m in matches if m["match_status"] in NEEDS_EXCEPTION and m["match_id"] not in with_exc]
    bank_rows = Counter(m["bank_line_id"] for m in matches if m["match_level"] == "BATCH_TO_BANK" and m["bank_line_id"])
    bank_cov = [b["bank_line_id"] for b in data["bank_statement_lines"] if bank_rows[b["bank_line_id"]] != 1]
    batch_seen = {m["batch_id"] for m in matches if m["match_level"] == "BATCH_TO_BANK"}
    batch_cov = [b["batch_id"] for b in data["settlement_batches"] if b["batch_id"] not in batch_seen]
    line_seen = {m["settlement_line_id"] for m in matches if m["match_level"] == "EVENT_TO_SETTLEMENT"}
    line_cov = [l["settlement_line_id"] for l in data["settlement_lines"] if l["settlement_line_id"] not in line_seen]
    event_seen = {m["event_id"] for m in matches if m["match_level"] == "EVENT_TO_SETTLEMENT"}
    settle_events = {e["event_id"] for e in data["processor_events"] if e["event_type"] in ("CAPTURED", "REFUNDED")}
    event_cov = sorted(settle_events - event_seen)
    ok = not (missing_exc or bank_cov or batch_cov or line_cov or event_cov)
    results.append(check("Every unmatched item is an exception; nothing silently dropped", ok,
                         f"{len(missing_exc)} unmatched decisions without exception; uncovered: bank lines "
                         f"{len(bank_cov)}, batches {len(batch_cov)}, settlement lines {len(line_cov)}, "
                         f"events {len(event_cov)}"))

    raw = len(data["processor_events"])
    unique = len({e["event_id"] for e in data["processor_events"]})
    dedup_ok = len(out["event_dedup_log"]) == raw - unique
    recon_files = ["reconciliation_matches.csv", "exceptions.csv", "resolutions.csv", "event_dedup_log.csv"]
    core_files = ["reconciliation_matches.csv", "exceptions.csv", "resolutions.csv"]
    recon_dir = os.path.join(scale_dir, "recon")
    with tempfile.TemporaryDirectory() as tmp:
        rerun = os.path.join(tmp, "rerun")
        reconcile.run(os.path.join(scale_dir, "data"), rerun, quiet=True)
        same_rerun = all(sha256_file(os.path.join(recon_dir, f)) == sha256_file(os.path.join(rerun, f)) for f in recon_files)
        # re-ingest the WHOLE event file a second time (new ingest ids) -> core results must not change
        data2 = os.path.join(tmp, "data2")
        shutil.copytree(os.path.join(scale_dir, "data"), data2)
        path = os.path.join(data2, "processor_events.csv")
        rows = read_csv(path)
        start = max(int(r["ingest_id"].split("-")[-1]) for r in rows)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
            for i, r in enumerate(rows, 1):
                w.writerow(dict(r, ingest_id=f"ING-{config.ID_YEAR}-{start + i:08d}"))
        reingest = os.path.join(tmp, "reingest")
        reconcile.run(data2, reingest, quiet=True)
        same_reingest = all(sha256_file(os.path.join(recon_dir, f)) == sha256_file(os.path.join(reingest, f)) for f in core_files)
    results.append(check("Duplicate events are idempotent", dedup_ok and same_rerun and same_reingest,
                         f"{raw - unique} duplicate rows ignored (log has {len(out['event_dedup_log'])}); "
                         f"identical output on re-run: {same_rerun}; identical matches/exceptions after "
                         f"re-ingesting all {raw:,} events again: {same_reingest}"))

    # 4. fee and refund treatment
    merchants = {m["merchant_id"]: m for m in data["merchants"]}
    orders = {o["payment_id"]: o for o in data["payment_orders"]}
    bad_fee = []
    for l in data["settlement_lines"]:
        m = merchants[orders[l["payment_id"]]["merchant_id"]]
        if l["line_type"] == "REFUND":
            good = Decimal(l["fee_amount"]) == 0 and Decimal(l["gross_amount"]) < 0
        else:
            want = money(Decimal(l["gross_amount"]) * Decimal(m["fee_rate_pct"]) / 100 + Decimal(m["fixed_fee"]), l["currency"])
            good = Decimal(l["fee_amount"]) == want and Decimal(l["gross_amount"]) > 0
        if not good or Decimal(l["net_amount"]) != Decimal(l["gross_amount"]) - Decimal(l["fee_amount"]):
            bad_fee.append(l["settlement_line_id"])
    bad_batch = [b["batch_id"] for b in data["settlement_batches"] if Decimal(b["net_amount"]) !=
                 Decimal(b["gross_captured"]) - Decimal(b["gross_refunded"]) - Decimal(b["fee_total"])]
    fee_exc = {e["exception_id"] for e in exceptions if e["exception_type"] == "FEE_DIFFERENCE"}
    fee_res = {r["exception_id"] for r in resolutions if r["action"] == "POST_FEE_ADJUSTMENT"}
    over_refund = [o["payment_id"] for o in data["payment_orders"]
                   if Decimal(o["refunded_amount"]) > Decimal(o["captured_amount"])]
    ok = not (bad_fee or bad_batch or over_refund) and fee_exc == fee_res
    results.append(check("Fee and refund treatment is consistent", ok,
                         f"line fee/sign errors {len(bad_fee)}, batch net errors {len(bad_batch)}, "
                         f"over-refunded orders {len(over_refund)}, fee differences all handled by "
                         f"POST_FEE_ADJUSTMENT: {fee_exc == fee_res}"))
    return results


def run(scale_dir, quiet=False):
    data = {n: read_csv(os.path.join(scale_dir, "data", f"{n}.csv"))
            for n in ("merchants", "payment_orders", "processor_events", "settlement_batches",
                      "settlement_lines", "bank_statement_lines")}
    out = {n: read_csv(os.path.join(scale_dir, "recon", f"{n}.csv"))
           for n in ("reconciliation_matches", "exceptions", "resolutions", "event_dedup_log")}
    gt = read_csv(os.path.join(scale_dir, "ground_truth", "ground_truth.csv"))

    scores = score_ground_truth(gt, out["exceptions"], out["reconciliation_matches"], out["event_dedup_log"])
    criteria = acceptance(scale_dir, data, out)
    result = {"ground_truth_scores": scores, "acceptance_criteria": criteria,
              "overall": "PASS" if all(c["status"] == "PASS" for c in criteria) else "FAIL"}
    write_json(os.path.join(scale_dir, "evaluation.json"), result)

    md = ["# Evaluation", "", f"Overall acceptance: **{result['overall']}**", "",
          f"* Anomaly recall: **{scores['anomaly_recall']}** ({scores['anomaly_cases_handled']}/{scores['anomaly_cases']})",
          f"* Scenario accuracy: **{scores['scenario_accuracy']}** ({scores['scenario_cases']} cases)",
          f"* Exception precision / recall / F1: **{scores['exception_precision']} / "
          f"{scores['exception_recall']} / {scores['exception_f1']}**", "",
          "## Acceptance criteria", "", "| Criterion | Status | Detail |", "|---|---|---|"]
    md += [f"| {c['criterion']} | {c['status']} | {c['detail']} |" for c in criteria]
    md += ["", "## By labelled issue type", "", "| Issue | Category | Expected | Handled | Recall |", "|---|---|---|---|---|"]
    md += [f"| {k} | {v['category']} | {v['expected']} | {v['handled']} | {v['recall']} |"
           for k, v in scores["by_issue_type"].items()]
    md += ["", "## By exception type", "", "| Exception | Raised | True positive | Precision |", "|---|---|---|---|"]
    md += [f"| {k} | {v['raised']} | {v['true_positive']} | {v['precision']} |"
           for k, v in scores["by_exception_type"].items()]
    with open(os.path.join(scale_dir, "evaluation.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    if not quiet:
        print(f"[evaluate] anomaly recall {scores['anomaly_recall']}, scenario accuracy {scores['scenario_accuracy']}, "
              f"exception precision {scores['exception_precision']} -> acceptance {result['overall']}")
        for c in criteria:
            print(f"    {c['status']}: {c['criterion']}")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="starter")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run(a.out or os.path.join("output", a.scale))
