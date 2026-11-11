import argparse
import json
import os
from collections import defaultdict
from html import escape

from common import read_csv


def table(headers, rows):
    head = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def badge(status):
    good = status in ("PASS", "MATCHED", "RESOLVED")
    return f'<span class="badge {"ok" if good else "bad"}">{escape(status)}</span>'


def trace(exc, matches, data):
    """Walk from an exception back to the source records."""
    steps = [f"Exception {exc['exception_id']} ({exc['exception_type']}) on {exc['entity_type']} {exc['entity_id']}"]
    m = matches.get(exc["match_id"])
    if m:
        steps.append(f"Decision {m['match_id']}: {m['match_level']} {m['match_status']} via {m['match_method']} "
                     f"(expected {m['expected_amount']} / actual {m['actual_amount']} {m['currency']})")
    ids = [exc["entity_id"]] + [x for x in exc["related_ids"].split(";") if x]
    if m:
        ids += [m["event_id"], m["settlement_line_id"], m["batch_id"], m["bank_line_id"]]
    seen = set()
    for i in ids:
        if not i or i in seen:
            continue
        seen.add(i)
        for label, index in data.items():
            if i in index:
                r = index[i]
                summary = ", ".join(f"{k}={v}" for k, v in list(r.items())[:7])
                steps.append(f"{label} {i}: {summary}")
                if label in ("ProcessorEvent", "SettlementLine") and r.get("payment_id") in data["PaymentOrder"]:
                    o = data["PaymentOrder"][r["payment_id"]]
                    steps.append(f"PaymentOrder {o['payment_id']}: merchant {o['merchant_id']}, "
                                 f"{o['amount']} {o['currency']}, status {o['status']}")
    return steps


def run(scale_dir, quiet=False):
    rd = lambda *p: read_csv(os.path.join(scale_dir, *p))
    metrics = json.load(open(os.path.join(scale_dir, "recon", "metrics.json")))
    evaluation = json.load(open(os.path.join(scale_dir, "evaluation.json")))
    validation = json.load(open(os.path.join(scale_dir, "validation_summary.json")))
    repro_path = os.path.join(scale_dir, "reproducibility_report.json")
    repro = json.load(open(repro_path)) if os.path.exists(repro_path) else None
    exceptions = rd("recon", "exceptions.csv")
    resolutions = rd("recon", "resolutions.csv")
    matches = {m["match_id"]: m for m in rd("recon", "reconciliation_matches.csv")}
    events = {}
    for e in rd("data", "processor_events.csv"):
        events.setdefault(e["event_id"], e)
    data = {
        "ProcessorEvent": events,
        "SettlementLine": {r["settlement_line_id"]: r for r in rd("data", "settlement_lines.csv")},
        "SettlementBatch": {r["batch_id"]: r for r in rd("data", "settlement_batches.csv")},
        "BankStatementLine": {r["bank_line_id"]: r for r in rd("data", "bank_statement_lines.csv")},
        "PaymentOrder": {r["payment_id"]: r for r in rd("data", "payment_orders.csv")},
    }
    history = defaultdict(list)
    for r in resolutions:
        history[r["exception_id"]].append(r)

    e2s, b2b, pe, bl = (metrics["event_to_settlement"], metrics["batch_to_bank"],
                        metrics["processor_events"], metrics["bank_lines"])
    gts = evaluation["ground_truth_scores"]
    kpis = [("Event match rate", f"{e2s['match_rate']:.2%}"), ("Batch auto-match rate", f"{b2b['auto_match_rate']:.2%}"),
            ("Exceptions", metrics["exceptions"]["total"]), ("Duplicates ignored", pe["duplicates_ignored"]),
            ("Anomaly recall", f"{gts['anomaly_recall']:.0%}"), ("Exception precision", f"{gts['exception_precision']:.0%}")]
    kpi_html = "".join(f'<div class="kpi"><div class="v">{escape(str(v))}</div><div class="l">{escape(k)}</div></div>'
                       for k, v in kpis)

    exc_rows = []
    for e in exceptions:
        steps = history[e["exception_id"]]
        exc_rows.append([e["exception_id"], e["exception_type"], e["severity"], e["entity_type"], e["entity_id"],
                         e["amount_difference"], e["currency"], steps[-1]["resulting_status"] if steps else "OPEN",
                         " -> ".join(f"{s['actor_role']}:{s['action']}" for s in steps)])

    traces = []
    done = set()
    for e in exceptions:
        if e["exception_type"] in done:
            continue
        done.add(e["exception_type"])
        lines = "".join(f"<li>{escape(s)}</li>" for s in trace(e, matches, data))
        traces.append(f"<h3>{escape(e['exception_type'])}</h3><ol>{lines}</ol>")

    amount_rows = [[c] + list(v.values()) for c, v in metrics["amounts_by_currency"].items()]
    crit = "".join(f"<tr><td>{escape(c['criterion'])}</td><td>{badge(c['status'])}</td><td>{escape(c['detail'])}</td></tr>"
                   for c in evaluation["acceptance_criteria"])
    issue_rows = [[k, v["category"], v["expected"], v["handled"], v["recall"]] for k, v in gts["by_issue_type"].items()]
    val_rows = [[r["check"], r["category"], r["status"], r["failures"], r["explained_by_ground_truth"]]
                for r in validation["results"] if r["category"] not in ("required", "enum", "id_format")]

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Payment reconciliation report</title>
<style>
body{{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:32px;color:#1d2433;max-width:1200px}}
h1{{margin-bottom:4px}} h2{{margin-top:36px;border-bottom:1px solid #dde2ea;padding-bottom:6px}}
.kpis{{display:flex;gap:12px;flex-wrap:wrap}} .kpi{{background:#f3f5f9;border-radius:8px;padding:14px 18px;min-width:150px}}
.kpi .v{{font-size:26px;font-weight:600}} .kpi .l{{color:#5b6475;font-size:13px}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}} th,td{{border:1px solid #dde2ea;padding:5px 8px;text-align:left}}
th{{background:#f3f5f9}} .badge{{padding:2px 8px;border-radius:10px;font-size:12px}} .ok{{background:#dff3e4;color:#14632d}}
.bad{{background:#fde4e1;color:#8a1c12}} ol li{{font-family:ui-monospace,Consolas,monospace;font-size:12px;margin:2px 0}}
.muted{{color:#5b6475}}
</style></head><body>
<h1>Payment reconciliation report</h1>
<div class="muted">Scale: {escape(validation['scale'])} | as of {escape(metrics['as_of'])} | validation {badge(validation['overall'])}
 | acceptance {badge(evaluation['overall'])} {('| reproducible ' + badge('PASS' if repro['identical'] else 'FAIL')) if repro else ''}</div>
<h2>Key numbers</h2><div class="kpis">{kpi_html}</div>
<h2>Flow</h2>
{table(["Stage", "Count"], [
    ["Webhook rows ingested", pe["rows_ingested"]], ["Unique processor events", pe["unique_events"]],
    ["Captured/refunded events to settle", e2s["events_to_settle"]], ["Matched to a settlement line", e2s["matched"]],
    ["Settlement batches", b2b["batches"]], ["Batches matched exactly", b2b["matched_exact"]],
    ["Batches matched within tolerance", b2b["matched_with_tolerance"]], ["Batches partially matched", b2b["partial"]],
    ["Batches with no payout", b2b["missing_payout"]], ["Bank lines total", bl["total"]],
    ["Bank lines from processor (in scope)", bl["in_scope_processor"]], ["Bank lines out of scope (kept, labelled)", bl["out_of_scope"]]])}
<h2>Amounts by currency</h2>
{table(["Currency", "Batch net total", "Auto-matched", "Rounding absorbed", "In exceptions"], amount_rows)}
<h2>Acceptance criteria</h2><table><thead><tr><th>Criterion</th><th>Status</th><th>Detail</th></tr></thead><tbody>{crit}</tbody></table>
<h2>Exceptions ({len(exceptions)})</h2>
{table(["ID", "Type", "Severity", "Entity", "Entity ID", "Difference", "Ccy", "Current status", "History"], exc_rows)}
<h2>Traceability (one example per exception type)</h2>{''.join(traces)}
<h2>Ground-truth evaluation</h2>
<p>Exception precision {gts['exception_precision']}, recall {gts['exception_recall']}, F1 {gts['exception_f1']}.</p>
{table(["Issue type", "Category", "Expected", "Handled", "Recall"], issue_rows)}
<h2>Data validation (key checks)</h2>
{table(["Check", "Category", "Status", "Failures", "Explained by ground truth"], val_rows)}
</body></html>"""
    path = os.path.join(scale_dir, "report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    if not quiet:
        print(f"[report] {path}")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="starter")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run(a.out or os.path.join("output", a.scale))
