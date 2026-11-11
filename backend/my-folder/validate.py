
import argparse
import os
import re
from collections import Counter, defaultdict
from decimal import Decimal

import config
from common import money, parse_date, parse_dt, read_csv, write_json
from schema import TABLES


class Report:
    def __init__(self, labelled_ids):
        self.labelled = labelled_ids
        self.results = []

    def add(self, name, category, checked, failures):
        """failures: list of record IDs that broke the rule."""
        unexplained = [f for f in failures if f not in self.labelled]
        if not failures:
            status = "PASS"
        elif not unexplained:
            status = "PASS_WITH_LABELLED_ANOMALIES"
        else:
            status = "FAIL"
        self.results.append({"check": name, "category": category, "status": status, "rows_checked": checked,
                             "failures": len(failures), "explained_by_ground_truth": len(failures) - len(unexplained),
                             "sample_unexplained": unexplained[:5]})


def generic_checks(rep, tables):
    for name, rows in tables.items():
        t = TABLES[name]
        pk = t["pk"]
        counts = Counter(r[pk] for r in rows)
        rep.add(f"{name}: primary key {pk} unique", "primary_key", len(rows), [k for k, n in counts.items() if n > 1])
        for c in t["columns"]:
            cname = c["name"]
            if c["required"]:
                rep.add(f"{name}.{cname} required", "required", len(rows), [r[pk] for r in rows if r[cname] == ""])
            if c["enum"]:
                allowed = set(c["enum"])
                rep.add(f"{name}.{cname} allowed values", "enum", len(rows),
                        [r[pk] for r in rows if r[cname] != "" and r[cname] not in allowed])
            if c["pattern"]:
                rx = re.compile(c["pattern"])
                rep.add(f"{name}.{cname} ID format", "id_format", len(rows),
                        [r[pk] for r in rows if r[cname] != "" and not rx.match(r[cname])])
            if c["fk"]:
                ref_table, ref_col = c["fk"].split(".")
                if ref_table in tables:
                    parent = {r[ref_col] for r in tables[ref_table]}
                    rep.add(f"{name}.{cname} -> {c['fk']}", "foreign_key", len(rows),
                            [r[pk] for r in rows if r[cname] != "" and r[cname] not in parent])


def domain_checks(rep, t, scale):
    p = config.SCALES[scale]
    orders = {o["payment_id"]: o for o in t["payment_orders"]}
    merchants = {m["merchant_id"]: m for m in t["merchants"]}
    attempts = {a["attempt_id"]: a for a in t["payment_attempts"]}
    batches = {b["batch_id"]: b for b in t["settlement_batches"]}

    
    targets = {"merchants": p["merchants"], "payment_orders": p["orders"],
               "payment_attempts": p["orders"] + p["extra_attempts"],
               "settlement_batches": p["settlement_days"] * len(config.CURRENCIES),
               "bank_statement_lines": p["bank_lines"]}
    for name, target in targets.items():
        actual = len(t[name])
        rep.results.append({"check": f"{name}: row count = {target}", "category": "volume",
                            "status": "PASS" if actual == target else "WARN", "rows_checked": actual,
                            "failures": 0 if actual == target else abs(actual - target),
                            "explained_by_ground_truth": 0, "sample_unexplained": []})

    
    seen, dup_rows = set(), []
    for e in sorted(t["processor_events"], key=lambda r: r["ingest_id"]):
        if e["event_id"] in seen:
            dup_rows.append(e["ingest_id"])
        seen.add(e["event_id"])
    rep.add("processor_events: one row per event_id", "duplicates", len(t["processor_events"]), dup_rows)
    events = {}
    for e in sorted(t["processor_events"], key=lambda r: r["ingest_id"]):
        events.setdefault(e["event_id"], e)
    seen, dup_lines = set(), []
    for line in sorted(t["settlement_lines"], key=lambda l: l["settlement_line_id"]):
        if line["event_id"] in seen:
            dup_lines.append(line["settlement_line_id"])
        seen.add(line["event_id"])
    rep.add("settlement_lines: one line per event_id", "duplicates", len(t["settlement_lines"]), dup_lines)

    
    rep.add("attempt time >= order created_at", "date_order", len(attempts),
            [a["attempt_id"] for a in attempts.values()
             if parse_dt(a["attempted_at"]) < parse_dt(orders[a["payment_id"]]["created_at"])])
    rep.add("event time >= attempt time", "date_order", len(events),
            [e["event_id"] for e in events.values()
             if parse_dt(e["event_at"]) < parse_dt(attempts[e["attempt_id"]]["attempted_at"])])
    rep.add("webhook received_at >= event_at", "date_order", len(t["processor_events"]),
            [e["ingest_id"] for e in t["processor_events"] if e["received_at"] < e["event_at"]])
    caps = {e["payment_id"]: e for e in events.values() if e["event_type"] == "CAPTURED"}
    refunds = [e for e in events.values() if e["event_type"] == "REFUNDED"]
    rep.add("refund after capture", "date_order", len(refunds),
            [r["event_id"] for r in refunds
             if r["payment_id"] not in caps or r["event_at"] <= caps[r["payment_id"]]["event_at"]])
    rep.add("settlement_date >= event_date", "date_order", len(t["settlement_lines"]),
            [l["settlement_line_id"] for l in t["settlement_lines"]
             if parse_date(batches[l["batch_id"]]["settlement_date"]) < parse_date(l["event_date"])])
    rep.add("fee_effective_from >= onboarded_date", "date_order", len(merchants),
            [m["merchant_id"] for m in merchants.values() if m["fee_effective_from"] < m["onboarded_date"]])

    # --- arithmetic ---
    lines_by_batch = defaultdict(list)
    for line in t["settlement_lines"]:
        lines_by_batch[line["batch_id"]].append(line)
    bad = []
    for bid, b in batches.items():
        ls = lines_by_batch[bid]
        gc = sum((Decimal(l["gross_amount"]) for l in ls if l["line_type"] == "CAPTURE"), Decimal(0))
        gr = -sum((Decimal(l["gross_amount"]) for l in ls if l["line_type"] == "REFUND"), Decimal(0))
        fee = sum((Decimal(l["fee_amount"]) for l in ls), Decimal(0))
        if (int(b["line_count"]) != len(ls) or Decimal(b["gross_captured"]) != gc or Decimal(b["gross_refunded"]) != gr
                or Decimal(b["fee_total"]) != fee or Decimal(b["net_amount"]) != gc - gr - fee
                or int(b["capture_count"]) + int(b["refund_count"]) != len(ls)):
            bad.append(bid)
    rep.add("batch totals = sum of lines; net = captured - refunded - fees", "arithmetic", len(batches), bad)
    rep.add("line net = gross - fee", "arithmetic", len(t["settlement_lines"]),
            [l["settlement_line_id"] for l in t["settlement_lines"]
             if Decimal(l["net_amount"]) != Decimal(l["gross_amount"]) - Decimal(l["fee_amount"])])
    bad = []
    for l in t["settlement_lines"]:
        m = merchants[orders[l["payment_id"]]["merchant_id"]]
        if l["line_type"] == "CAPTURE":
            want = money(Decimal(l["gross_amount"]) * Decimal(m["fee_rate_pct"]) / 100 + Decimal(m["fixed_fee"]), l["currency"])
        else:
            want = money(0, l["currency"])
        if Decimal(l["fee_amount"]) != want:
            bad.append(l["settlement_line_id"])
    rep.add("fee = round(gross x rate% + fixed) for captures, 0 for refunds", "arithmetic", len(t["settlement_lines"]), bad)
    decimals_bad = []
    for name, field_list in {"payment_orders": ["amount"], "processor_events": ["amount"],
                             "settlement_lines": ["gross_amount", "fee_amount", "net_amount"],
                             "settlement_batches": ["net_amount", "fee_total"],
                             "bank_statement_lines": ["amount"]}.items():
        pk = TABLES[name]["pk"]
        for r in t[name]:
            places = config.CURRENCIES[r["currency"]]["decimals"]
            for f in field_list:
                if (len(r[f].split(".")[1]) if "." in r[f] else 0) != places:
                    decimals_bad.append(r[pk])
    rep.add("amounts rounded to currency minor unit (JPY 0 dp)", "arithmetic", 0, decimals_bad)
    ev_by_pay = defaultdict(list)
    for e in events.values():
        ev_by_pay[e["payment_id"]].append(e)
    bad = []
    for pid, o in orders.items():
        cap = sum((Decimal(e["amount"]) for e in ev_by_pay[pid] if e["event_type"] == "CAPTURED"), Decimal(0))
        ref = sum((Decimal(e["amount"]) for e in ev_by_pay[pid] if e["event_type"] == "REFUNDED"), Decimal(0))
        if Decimal(o["captured_amount"]) != cap or Decimal(o["refunded_amount"]) != ref or ref > cap:
            bad.append(pid)
    rep.add("order captured/refunded = sum of unique events; refund <= capture", "arithmetic", len(orders), bad)

    # --- lifecycle ---
    att_by_pay = defaultdict(list)
    for a in attempts.values():
        att_by_pay[a["payment_id"]].append(a)
    bad = []
    for pid, o in orders.items():
        atts = sorted(att_by_pay[pid], key=lambda a: int(a["attempt_no"]))
        nums = [int(a["attempt_no"]) for a in atts]
        wins = [a for a in atts if a["outcome"] == "SUCCEEDED"]
        types = Counter(e["event_type"] for e in ev_by_pay[pid])
        if (nums != list(range(1, len(atts) + 1)) or len(wins) > 1 or (wins and wins[0] is not atts[-1])
                or int(o["attempt_count"]) != len(atts) or types["CAPTURED"] != len(wins)
                or types["AUTHORIZED"] != len(wins) or types["FAILED"] != len(atts) - len(wins)
                or (types["REFUNDED"] and not wins)):
            bad.append(pid)
    rep.add("attempt sequence and event lifecycle per order", "lifecycle", len(orders), bad)
    bad = []
    for pid, o in orders.items():
        cap, ref = Decimal(o["captured_amount"]), Decimal(o["refunded_amount"])
        want = "FAILED" if cap == 0 else "CAPTURED" if ref == 0 else "REFUNDED" if ref >= cap else "PARTIALLY_REFUNDED"
        if o["status"] != want:
            bad.append(pid)
    rep.add("order status derived from events", "lifecycle", len(orders), bad)
    rep.add("event payment/currency consistent with attempt and order", "lifecycle", len(events),
            [e["event_id"] for e in events.values()
             if attempts[e["attempt_id"]]["payment_id"] != e["payment_id"]
             or orders[e["payment_id"]]["currency"] != e["currency"]])
    rep.add("settlement line currency = batch currency", "lifecycle", len(t["settlement_lines"]),
            [l["settlement_line_id"] for l in t["settlement_lines"] if l["currency"] != batches[l["batch_id"]]["currency"]])

    # --- coverage ---
    settled = {l["event_id"] for l in t["settlement_lines"]}
    to_settle = [e for e in events.values() if e["event_type"] in ("CAPTURED", "REFUNDED")]
    rep.add("every captured/refunded event appears in settlement", "coverage", len(to_settle),
            [e["event_id"] for e in to_settle if e["event_id"] not in settled])


def run(scale_dir, scale, quiet=False):
    tables = {}
    for name, t in TABLES.items():
        path = os.path.join(scale_dir, t["folder"], f"{name}.csv")
        if os.path.exists(path):
            tables[name] = read_csv(path)
    gt_path = os.path.join(scale_dir, "ground_truth", "ground_truth.csv")
    gt = read_csv(gt_path)
    labelled = set()
    for g in gt:
        labelled.add(g["entity_id"])
        labelled.update(x for x in g["related_id"].split(";") if x)

    rep = Report(labelled)
    generic_checks(rep, tables)
    domain_checks(rep, tables, scale)

    leaked = [f"{n}.{c}" for n, rows in tables.items() if rows
              for c in rows[0] if c in ("issue_type", "expected_decision", "ground_truth", "case_id")]
    rep.add("ground truth not leaked into input/output columns", "ground_truth", len(tables), leaked)
    rep.add("ground truth stored outside data folder", "ground_truth", 1,
            [] if not os.path.exists(os.path.join(scale_dir, "data", "ground_truth.csv")) else ["data/ground_truth.csv"])

    statuses = Counter(r["status"] for r in rep.results)
    summary = {"scale": scale, "checks": len(rep.results), "status_counts": dict(statuses),
               "overall": "FAIL" if statuses["FAIL"] else "PASS", "results": rep.results}
    write_json(os.path.join(scale_dir, "validation_summary.json"), summary)
    md = ["# Validation summary", "", f"Scale: **{scale}**, overall: **{summary['overall']}**", "",
          "| Check | Category | Status | Rows | Failures | Labelled |", "|---|---|---|---|---|---|"]
    md += [f"| {r['check']} | {r['category']} | {r['status']} | {r['rows_checked']} | {r['failures']} | "
           f"{r['explained_by_ground_truth']} |" for r in rep.results]
    with open(os.path.join(scale_dir, "validation_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    if not quiet:
        print(f"[validate] {len(rep.results)} checks: {dict(statuses)} -> overall {summary['overall']}")
        for r in rep.results:
            if r["status"] in ("FAIL", "WARN"):
                print(f"    {r['status']}: {r['check']} {r['sample_unexplained']}")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="starter")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run(a.out or os.path.join("output", a.scale), a.scale)
