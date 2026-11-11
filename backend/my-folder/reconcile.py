import argparse
import os
import re
from collections import Counter, defaultdict
from decimal import Decimal

import config
from common import (money, parse_date, parse_dt, read_csv, save_table, tolerance,
                    write_csv, write_json)
from schema import INPUT_TABLES, TABLES

Y = config.ID_YEAR
RUN_DATE = config.AS_OF_TIMESTAMP[:10]
REF_PATTERN = re.compile(rf"SET-\d{{4}}-\d{{6}}")
MATCHED = ("MATCHED", "MATCHED_WITH_TOLERANCE")

SEVERITY = {
    "MISSING_FROM_SETTLEMENT": "HIGH", "DUPLICATE_SETTLEMENT_LINE": "HIGH", "ORPHAN_SETTLEMENT_LINE": "MEDIUM",
    "LINE_AMOUNT_MISMATCH": "HIGH", "LINE_CURRENCY_MISMATCH": "HIGH", "LATE_SETTLEMENT": "LOW",
    "REFUND_BEFORE_CAPTURE": "MEDIUM", "EVENT_PAYLOAD_CONFLICT": "HIGH", "FEE_DIFFERENCE": "LOW",
    "AMOUNT_MISMATCH": "HIGH", "CURRENCY_MISMATCH": "HIGH", "DATE_OUT_OF_WINDOW": "LOW",
    "DUPLICATE_PAYOUT": "HIGH", "UNMATCHED_BANK_LINE": "MEDIUM", "AMBIGUOUS_BANK_MATCH": "MEDIUM",
    "MISSING_PAYOUT": "HIGH",
}

# exception type -> list of (actor role, action, resulting status, note). Each step = one resolution row.
ESCALATE = [("operations_analyst", "ESCALATE", "ESCALATED", "Needs risk/compliance review."),
            ("risk_compliance_reviewer", "COMPLIANCE_REVIEW", "UNDER_COMPLIANCE_REVIEW",
             "Reviewer assigned; funds held until cleared.")]
PLAYBOOK = {
    "FEE_DIFFERENCE": [("operations_analyst", "POST_FEE_ADJUSTMENT", "RESOLVED",
                        "Difference equals batch fee_total; fee booked as a separate expense.")],
    "DUPLICATE_SETTLEMENT_LINE": [("operations_analyst", "RAISE_PROCESSOR_CLAIM", "PENDING_PROCESSOR",
                                   "Same event settled twice; claim the duplicated amount back.")],
    "MISSING_FROM_SETTLEMENT": [("operations_analyst", "RAISE_PROCESSOR_CLAIM", "PENDING_PROCESSOR",
                                 "Captured event never settled; ask processor to include it.")],
    "MISSING_PAYOUT": [("operations_analyst", "CHASE_PAYOUT", "PENDING_PROCESSOR",
                        "Batch closed but no bank credit inside the date window.")],
    "UNMATCHED_BANK_LINE": [("operations_analyst", "INVESTIGATE", "IN_REVIEW",
                             "Processor credit with no batch; parked in suspense account.")],
    "CURRENCY_MISMATCH": ESCALATE,
    "AMOUNT_MISMATCH": ESCALATE,
    "REFUND_BEFORE_CAPTURE": ESCALATE,
    "EVENT_PAYLOAD_CONFLICT": ESCALATE,
    "DUPLICATE_PAYOUT": ESCALATE,
}
DEFAULT_PLAYBOOK = [("operations_analyst", "INVESTIGATE", "IN_REVIEW", "Manual investigation required.")]


class Book:
    """Keeps the decision records (matches) and exceptions with deterministic IDs."""

    def __init__(self):
        self.matches, self.exceptions = [], []

    def match(self, **fields):
        row = {c["name"]: "" for c in TABLES["reconciliation_matches"]["columns"]}
        row.update({k: ("" if v is None else str(v)) for k, v in fields.items()})
        row["match_id"] = f"REC-{Y}-{len(self.matches) + 1:06d}"
        row["matched_on"] = RUN_DATE
        self.matches.append(row)
        return row["match_id"]

    def exception(self, etype, entity_type, entity_id, rule, match_id="", related="", diff="", currency=""):
        self.exceptions.append({
            "exception_id": f"EXC-{Y}-{len(self.exceptions) + 1:06d}", "exception_type": etype,
            "severity": SEVERITY[etype], "entity_type": entity_type, "entity_id": entity_id,
            "related_ids": related, "match_id": match_id, "amount_difference": str(diff),
            "currency": currency, "rule": rule, "status": "OPEN", "created_at": config.AS_OF_TIMESTAMP})


# ---------------------------------------------------------------------------
def dedupe_events(rows, book):
    """Keep the first row of each event_id; log every other row. Running twice gives the same result."""
    payload = ("payment_id", "attempt_id", "event_type", "amount", "currency", "event_at")
    first, unique, log = {}, [], []
    for row in sorted(rows, key=lambda r: r["ingest_id"]):
        kept = first.get(row["event_id"])
        if kept is None:
            first[row["event_id"]] = row
            unique.append(row)
            continue
        same = all(row[k] == kept[k] for k in payload)
        log.append({"dedup_id": f"DUP-{Y}-{len(log) + 1:06d}", "ingest_id": row["ingest_id"],
                    "event_id": row["event_id"], "duplicate_of_ingest_id": kept["ingest_id"],
                    "reason": "DUPLICATE_INGESTION" if row["delivery_id"] == kept["delivery_id"] else "DUPLICATE_WEBHOOK",
                    "payload_identical": "Y" if same else "N", "decision": "IGNORED_IDEMPOTENT"})
        if not same:
            book.exception("EVENT_PAYLOAD_CONFLICT", "ProcessorEvent", row["ingest_id"],
                           "duplicate event_id with a different payload", related=kept["ingest_id"])
    return unique, log


def check_refund_order(events, book):
    captures = {e["payment_id"]: e for e in events if e["event_type"] == "CAPTURED"}
    for e in events:
        if e["event_type"] != "REFUNDED":
            continue
        cap = captures.get(e["payment_id"])
        if cap is None or parse_dt(e["event_at"]) < parse_dt(cap["event_at"]):
            book.exception("REFUND_BEFORE_CAPTURE", "ProcessorEvent", e["event_id"],
                           "refund event_at must be later than the capture event_at",
                           related=f"{e['payment_id']};{cap['event_id'] if cap else 'NO_CAPTURE'}",
                           currency=e["currency"])


def match_events_to_settlement(events, lines, batches, book):
    by_event = defaultdict(list)
    for line in sorted(lines, key=lambda l: l["settlement_line_id"]):
        by_event[line["event_id"]].append(line)
    settleable = [e for e in events if e["event_type"] in ("CAPTURED", "REFUNDED")]
    settleable_ids = {e["event_id"] for e in settleable}

    for e in settleable:
        cur, eid = e["currency"], e["event_id"]
        sign = 1 if e["event_type"] == "CAPTURED" else -1
        expected = money(Decimal(e["amount"]) * sign, cur)
        found = by_event.get(eid, [])
        if not found:
            mid = book.match(match_level="EVENT_TO_SETTLEMENT", event_id=eid, match_status="UNMATCHED",
                             match_method="NONE", expected_amount=expected, currency=cur, tolerance=tolerance(cur))
            book.exception("MISSING_FROM_SETTLEMENT", "ProcessorEvent", eid,
                           "every captured/refunded event must appear in exactly one settlement line",
                           match_id=mid, related=e["payment_id"], diff=expected, currency=cur)
            continue

        line, extras = found[0], found[1:]
        actual = Decimal(line["gross_amount"])
        diff = actual - expected
        batch = batches.get(line["batch_id"])
        problems = []
        if line["currency"] != cur:
            problems.append(("LINE_CURRENCY_MISMATCH", "settlement line currency must equal event currency"))
        elif abs(diff) > tolerance(cur):
            problems.append(("LINE_AMOUNT_MISMATCH", "settlement line amount must equal event amount"))
        lag = (parse_date(batch["settlement_date"]) - parse_dt(e["event_at"]).date()).days if batch else None
        if lag is None or not 0 <= lag <= config.SETTLEMENT_WINDOW_DAYS:
            problems.append(("LATE_SETTLEMENT", f"settlement must be 0-{config.SETTLEMENT_WINDOW_DAYS} days after event"))
        mid = book.match(match_level="EVENT_TO_SETTLEMENT", event_id=eid,
                         settlement_line_id=line["settlement_line_id"], batch_id=line["batch_id"],
                         match_status="PARTIAL" if problems else "MATCHED", match_method="EVENT_ID",
                         expected_amount=expected, actual_amount=actual, difference=diff, currency=cur,
                         tolerance=tolerance(cur))
        for etype, rule in problems:
            book.exception(etype, "SettlementLine", line["settlement_line_id"], rule, match_id=mid,
                           related=eid, diff=diff, currency=cur)
        for extra in extras:
            mid = book.match(match_level="EVENT_TO_SETTLEMENT", event_id=eid,
                             settlement_line_id=extra["settlement_line_id"], batch_id=extra["batch_id"],
                             match_status="DUPLICATE", match_method="EVENT_ID", expected_amount=money(0, cur),
                             actual_amount=extra["gross_amount"], difference=extra["gross_amount"],
                             currency=cur, tolerance=tolerance(cur))
            book.exception("DUPLICATE_SETTLEMENT_LINE", "SettlementLine", extra["settlement_line_id"],
                           "an event may be settled only once", match_id=mid,
                           related=f"{eid};{line['settlement_line_id']}", diff=extra["gross_amount"], currency=cur)

    for line in sorted(lines, key=lambda l: l["settlement_line_id"]):
        if line["event_id"] not in settleable_ids:
            mid = book.match(match_level="EVENT_TO_SETTLEMENT", event_id=line["event_id"],
                             settlement_line_id=line["settlement_line_id"], batch_id=line["batch_id"],
                             match_status="UNMATCHED", match_method="NONE", actual_amount=line["gross_amount"],
                             currency=line["currency"])
            book.exception("ORPHAN_SETTLEMENT_LINE", "SettlementLine", line["settlement_line_id"],
                           "settlement line must point to a captured/refunded event", match_id=mid,
                           related=line["event_id"], currency=line["currency"])


def payout_date_ok(bank_line, batch):
    lag = (parse_date(bank_line["value_date"]) - parse_date(batch["settlement_date"])).days
    return 0 <= lag <= config.BANK_DATE_WINDOW_DAYS


def compare_payout(book, line, batch, method):
    cur = batch["currency"]
    expected, actual = Decimal(batch["net_amount"]), Decimal(line["amount"])
    diff = actual - expected
    problems = []
    if line["currency"] != cur:
        problems.append(("CURRENCY_MISMATCH", f"bank currency {line['currency']} must equal batch currency {cur}"))
    elif abs(diff) > tolerance(cur):
        if abs(abs(diff) - Decimal(batch["fee_total"])) <= tolerance(cur):
            problems.append(("FEE_DIFFERENCE", "bank amount differs from batch net by exactly the batch fee_total"))
        else:
            problems.append(("AMOUNT_MISMATCH", f"bank amount must equal batch net within {tolerance(cur)} {cur}"))
    if not payout_date_ok(line, batch):
        problems.append(("DATE_OUT_OF_WINDOW", f"value date must be 0-{config.BANK_DATE_WINDOW_DAYS} days after settlement"))
    status = "PARTIAL" if problems else ("MATCHED" if diff == 0 else "MATCHED_WITH_TOLERANCE")
    mid = book.match(match_level="BATCH_TO_BANK", batch_id=batch["batch_id"], bank_line_id=line["bank_line_id"],
                     match_status=status, match_method=method, expected_amount=expected, actual_amount=actual,
                     difference=diff, currency=cur, tolerance=tolerance(cur))
    for etype, rule in problems:
        book.exception(etype, "BankStatementLine", line["bank_line_id"], rule, match_id=mid,
                       related=batch["batch_id"], diff=diff, currency=cur)


def match_batches_to_bank(batches, bank_lines, book):
    in_scope = [b for b in bank_lines if b["counterparty"] == config.PROCESSOR_NAME]
    claimed, deferred = set(), []

    # Pass 1: by SET reference
    for line in in_scope:
        found = REF_PATTERN.search(line["reference"] or "")
        ref = found.group(0) if found else None
        if ref in batches and ref not in claimed:
            claimed.add(ref)
            compare_payout(book, line, batches[ref], "REFERENCE")
        elif ref in claimed:
            mid = book.match(match_level="BATCH_TO_BANK", batch_id=ref, bank_line_id=line["bank_line_id"],
                             match_status="DUPLICATE", match_method="REFERENCE", actual_amount=line["amount"],
                             currency=line["currency"])
            book.exception("DUPLICATE_PAYOUT", "BankStatementLine", line["bank_line_id"],
                           "a batch can be paid out only once", match_id=mid, related=ref,
                           diff=line["amount"], currency=line["currency"])
        else:
            deferred.append(line)

    # Pass 2: no usable reference -> amount + currency + date window, must be a unique candidate
    for line in deferred:
        cur, amount = line["currency"], Decimal(line["amount"])
        candidates = [b for bid, b in batches.items() if bid not in claimed and b["currency"] == cur
                      and abs(amount - Decimal(b["net_amount"])) <= tolerance(cur) and payout_date_ok(line, b)]
        if len(candidates) == 1:
            claimed.add(candidates[0]["batch_id"])
            compare_payout(book, line, candidates[0], "AMOUNT_CURRENCY_DATE")
            continue
        mid = book.match(match_level="BATCH_TO_BANK", bank_line_id=line["bank_line_id"], match_status="UNMATCHED",
                         match_method="NONE", actual_amount=amount, currency=cur)
        etype = "AMBIGUOUS_BANK_MATCH" if candidates else "UNMATCHED_BANK_LINE"
        book.exception(etype, "BankStatementLine", line["bank_line_id"],
                       "every processor bank line must match exactly one batch", match_id=mid,
                       related=";".join(b["batch_id"] for b in candidates), diff=amount, currency=cur)

    # Batches nobody paid
    for bid in sorted(batches):
        if bid not in claimed:
            b = batches[bid]
            mid = book.match(match_level="BATCH_TO_BANK", batch_id=bid, match_status="UNMATCHED", match_method="NONE",
                             expected_amount=b["net_amount"], currency=b["currency"], tolerance=tolerance(b["currency"]))
            book.exception("MISSING_PAYOUT", "SettlementBatch", bid,
                           f"every batch needs a bank credit within {config.BANK_DATE_WINDOW_DAYS} days",
                           match_id=mid, diff=f"-{b['net_amount']}", currency=b["currency"])

    # Everything else on the statement is kept and labelled, never silently dropped
    for line in bank_lines:
        if line["counterparty"] != config.PROCESSOR_NAME:
            book.match(match_level="BATCH_TO_BANK", bank_line_id=line["bank_line_id"], match_status="OUT_OF_SCOPE",
                       match_method="COUNTERPARTY_FILTER", actual_amount=line["amount"], currency=line["currency"])


def build_resolutions(exceptions):
    rows = []
    for exc in exceptions:
        for step, (role, action, status, note) in enumerate(PLAYBOOK.get(exc["exception_type"], DEFAULT_PLAYBOOK), 1):
            rows.append({"resolution_id": f"RES-{Y}-{len(rows) + 1:06d}", "exception_id": exc["exception_id"],
                         "step_no": step, "actor_role": role, "action": action, "resulting_status": status,
                         "recorded_at": config.AS_OF_TIMESTAMP, "note": note})
    return rows


def merchant_summary(t, exceptions):
    """Customer/account-holder view: what each merchant was settled and what is still open."""
    pay_to_mer = {p["payment_id"]: p["merchant_id"] for p in t["payment_orders"]}
    line_to_pay = {l["settlement_line_id"]: l["payment_id"] for l in t["settlement_lines"]}
    event_to_pay = {e["event_id"]: e["payment_id"] for e in t["processor_events"]}
    ingest_to_pay = {e["ingest_id"]: e["payment_id"] for e in t["processor_events"]}
    sums = defaultdict(lambda: defaultdict(Decimal))
    for line in t["settlement_lines"]:
        s = sums[pay_to_mer[line["payment_id"]]]
        key = "captured_gross" if line["line_type"] == "CAPTURE" else "refunded_gross"
        s[key] += abs(Decimal(line["gross_amount"]))
        s["fees"] += Decimal(line["fee_amount"])
        s["net_settled"] += Decimal(line["net_amount"])
        s["settled_lines"] += 1
    open_exc = Counter()
    for e in exceptions:
        pid = line_to_pay.get(e["entity_id"]) or event_to_pay.get(e["entity_id"]) or ingest_to_pay.get(e["entity_id"])
        if pid:
            open_exc[pay_to_mer[pid]] += 1
    rows = []
    for m in t["merchants"]:
        s, cur = sums[m["merchant_id"]], m["settlement_currency"]
        rows.append({"merchant_id": m["merchant_id"], "merchant_name": m["merchant_name"], "currency": cur,
                     "settled_lines": int(s["settled_lines"]),
                     "captured_gross": money(s["captured_gross"], cur), "refunded_gross": money(s["refunded_gross"], cur),
                     "fees": money(s["fees"], cur), "net_settled": money(s["net_settled"], cur),
                     "open_exceptions": open_exc[m["merchant_id"]]})
    return rows


def build_metrics(t, unique, dedup, book, resolutions):
    m = book.matches
    ev = [r for r in m if r["match_level"] == "EVENT_TO_SETTLEMENT"]
    bb = [r for r in m if r["match_level"] == "BATCH_TO_BANK"]
    batch_rows = [r for r in bb if r["batch_id"]]
    in_scope = [r for r in bb if r["match_status"] != "OUT_OF_SCOPE" and r["bank_line_id"]]
    unique_ids = {e["event_id"] for e in unique}
    settleable = [r for r in ev if r["match_status"] != "DUPLICATE" and r["event_id"] in unique_ids]
    final_status = {}
    for r in resolutions:
        final_status[r["exception_id"]] = r["resulting_status"]

    amounts = {}
    for cur in config.CURRENCIES:
        rows = [r for r in batch_rows if r["currency"] == cur]
        net = sum((Decimal(b["net_amount"]) for b in t["settlement_batches"] if b["currency"] == cur), Decimal(0))
        ok = [r for r in rows if r["match_status"] in MATCHED]
        amounts[cur] = {
            "batch_net_total": str(money(net, cur)),
            "auto_matched_amount": str(money(sum((Decimal(r["expected_amount"]) for r in ok), Decimal(0)), cur)),
            "rounding_difference_absorbed": str(money(sum((Decimal(r["difference"]) for r in ok), Decimal(0)), cur)),
            "amount_in_exceptions": str(money(net - sum((Decimal(r["expected_amount"]) for r in ok), Decimal(0)), cur)),
        }

    def rate(a, b):
        return round(a / b, 4) if b else None

    sc = Counter(r["match_status"] for r in batch_rows)
    return {
        "as_of": config.AS_OF_TIMESTAMP,
        "rules": {"settlement_window_days": config.SETTLEMENT_WINDOW_DAYS,
                  "bank_date_window_days": config.BANK_DATE_WINDOW_DAYS,
                  "amount_tolerance": {c: i["tolerance"] for c, i in config.CURRENCIES.items()}},
        "processor_events": {"rows_ingested": len(t["processor_events"]), "unique_events": len(unique),
                             "duplicates_ignored": len(dedup),
                             "by_reason": dict(Counter(d["reason"] for d in dedup))},
        "event_to_settlement": {
            "events_to_settle": len(settleable),
            "matched": sum(r["match_status"] == "MATCHED" for r in settleable),
            "partial": sum(r["match_status"] == "PARTIAL" for r in settleable),
            "missing": sum(r["match_status"] == "UNMATCHED" for r in settleable),
            "duplicate_lines": sum(r["match_status"] == "DUPLICATE" for r in ev),
            "match_rate": rate(sum(r["match_status"] == "MATCHED" for r in settleable), len(settleable))},
        "batch_to_bank": {
            "batches": len(t["settlement_batches"]),
            "matched_exact": sc["MATCHED"], "matched_with_tolerance": sc["MATCHED_WITH_TOLERANCE"],
            "matched_by_amount_fallback": sum(r["match_method"] == "AMOUNT_CURRENCY_DATE" for r in batch_rows),
            "partial": sc["PARTIAL"], "missing_payout": sc["UNMATCHED"],
            "auto_match_rate": rate(sc["MATCHED"] + sc["MATCHED_WITH_TOLERANCE"], len(t["settlement_batches"]))},
        "bank_lines": {
            "total": len(t["bank_statement_lines"]), "in_scope_processor": len(in_scope),
            "out_of_scope": sum(r["match_status"] == "OUT_OF_SCOPE" for r in bb),
            "matched": sum(r["match_status"] in MATCHED for r in in_scope),
            "partial": sum(r["match_status"] == "PARTIAL" for r in in_scope),
            "unmatched": sum(r["match_status"] in ("UNMATCHED", "DUPLICATE") for r in in_scope)},
        "amounts_by_currency": amounts,
        "exceptions": {"total": len(book.exceptions),
                       "by_type": dict(sorted(Counter(e["exception_type"] for e in book.exceptions).items())),
                       "by_severity": dict(Counter(e["severity"] for e in book.exceptions)),
                       "by_current_status": dict(Counter(final_status.values()))},
    }


def run(data_dir, out_dir, quiet=False):
    t = {name: read_csv(os.path.join(data_dir, f"{name}.csv")) for name in INPUT_TABLES}
    batches = {b["batch_id"]: b for b in t["settlement_batches"]}
    book = Book()

    unique, dedup = dedupe_events(t["processor_events"], book)
    check_refund_order(unique, book)
    match_events_to_settlement(unique, t["settlement_lines"], batches, book)
    match_batches_to_bank(batches, t["bank_statement_lines"], book)
    resolutions = build_resolutions(book.exceptions)

    save_table(out_dir, "event_dedup_log", dedup, with_json=False)
    save_table(out_dir, "reconciliation_matches", book.matches, with_json=False)
    save_table(out_dir, "exceptions", book.exceptions)
    save_table(out_dir, "resolutions", resolutions)
    summary = merchant_summary(t, book.exceptions)
    write_csv(os.path.join(out_dir, "merchant_summary.csv"), summary, list(summary[0].keys()))
    metrics = build_metrics(t, unique, dedup, book, resolutions)
    write_json(os.path.join(out_dir, "metrics.json"), metrics)
    write_json(os.path.join(out_dir, "run_config.json"),
               {"approved_by_role": "system_administrator", "as_of": config.AS_OF_TIMESTAMP,
                "processor_counterparty": config.PROCESSOR_NAME, **metrics["rules"]})
    if not quiet:
        print(f"[reconcile] {len(book.matches):,} decisions, {len(book.exceptions)} exceptions -> {out_dir}")
        print(f"    event match rate {metrics['event_to_settlement']['match_rate']}, "
              f"batch auto-match rate {metrics['batch_to_bank']['auto_match_rate']}")
    return metrics


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="starter")
    ap.add_argument("--out", default=None, help="scale folder, default output/<scale>")
    a = ap.parse_args()
    root = a.out or os.path.join("output", a.scale)
    run(os.path.join(root, "data"), os.path.join(root, "recon"))
