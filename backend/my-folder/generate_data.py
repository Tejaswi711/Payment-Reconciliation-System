import argparse
import os
import platform
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import config
from common import (business_days, fmt_dt, minor_unit, money, save_table,
                    sha256_file, write_csv, write_json)
from schema import CATEGORIES, DECLINE_CODES, PAYMENT_METHODS

Y = config.ID_YEAR
R = config.RATES
CURRENCY_CODES = list(config.CURRENCIES)
CURRENCY_WEIGHTS = [config.CURRENCIES[c]["weight"] for c in CURRENCY_CODES]

ADJECTIVES = ["Blue", "Golden", "Rapid", "Green", "Urban", "Silver", "Bright", "Happy", "North", "Royal",
              "Smart", "Fresh", "Prime", "Lucky", "Coastal", "Metro", "Swift", "Bold", "Quiet", "Sunny"]
NOUNS = ["Harbor", "Pixel", "Garden", "Market", "Bakery", "Studio", "Outfitters", "Gadgets", "Travel",
         "Kitchen", "Books", "Fitness", "Threads", "Labs", "Supply", "Cafe", "Motors", "Home", "Games", "Pets"]
SUFFIXES = ["Ltd", "LLC", "GmbH", "Co", "Store", "Group"]

OTHER_BANK_ACTIVITY = [
    ("Customer bank transfer", "VARIOUS CUSTOMERS", 1, 50, 8000, "TRF"),
    ("Supplier payment", "ACME LOGISTICS LTD", -1, 100, 15000, "INV"),
    ("Payroll", "PAYROLL SERVICES", -1, 2000, 40000, "PAY-RUN"),
    ("Office rent", "CITY PROPERTIES LLC", -1, 1500, 9000, "RENT"),
    ("Bank charges", "BANK", -1, 1, 60, "CHG"),
    ("Interest received", "BANK", 1, 1, 300, "INT"),
    ("Tax payment", "TAX AUTHORITY", -1, 500, 20000, "TAX"),
]

SPEC_TEXT = {
    "DUPLICATE_SETTLEMENT_LINE": "Duplicate settlement line",
    "FEE_DIFFERENCE": "Bank amount differs by fee",
    "REFUND_BEFORE_CAPTURE": "Refund appears before capture",
    "MISSING_FROM_SETTLEMENT": "Unmatched record silently dropped",
    "MISSING_PAYOUT": "Unmatched record silently dropped",
    "UNMATCHED_BANK_LINE": "Unmatched record silently dropped",
    "CURRENCY_MISMATCH": "Currency mismatch",
    "DUPLICATE_INGESTION": "Same processor event ingested twice",
    "DUPLICATE_WEBHOOK": "Duplicate webhooks (baseline coverage)",
    "DELAYED_SETTLEMENT": "Delayed settlements (baseline coverage)",
    "DELAYED_PAYOUT": "Delayed settlements (baseline coverage)",
    "ROUNDING_DIFFERENCE": "Currency rounding (baseline coverage)",
}


class GroundTruth:
    """Collects labels. IDs are read at the end because some IDs are assigned late."""

    def __init__(self):
        self.items = []

    def add(self, category, issue_type, entity_type, record, id_field, expected, related="", note=""):
        self.items.append({"category": category, "issue_type": issue_type, "entity_type": entity_type,
                           "record": record, "id_field": id_field, "expected": expected,
                           "related": related, "note": note})

    def rows(self):
        rows = [{"category": it["category"], "issue_type": it["issue_type"],
                 "spec_edge_case": SPEC_TEXT[it["issue_type"]], "entity_type": it["entity_type"],
                 "entity_id": it["record"][it["id_field"]], "related_id": it["related"],
                 "expected_decision": it["expected"], "note": it["note"]} for it in self.items]
        rows.sort(key=lambda r: (r["category"], r["issue_type"], r["entity_id"]))
        for i, r in enumerate(rows, 1):
            r["case_id"] = f"GT-{i:06d}"
        return rows


def make_merchants(rng, count):
    merchants, weights = [], []
    for i in range(1, count + 1):
        cur = rng.choices(CURRENCY_CODES, weights=CURRENCY_WEIGHTS)[0]
        info = config.CURRENCIES[cur]
        onboarded = date(2025, 1, 1) + timedelta(days=rng.randint(0, 364))
        merchants.append({
            "merchant_id": f"MER-{i:06d}",
            "merchant_name": f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)} {rng.choice(SUFFIXES)}",
            "country": rng.choice(info["countries"]),
            "settlement_currency": cur,
            "category": rng.choice(CATEGORIES),
            "fee_rate_pct": rng.choice(["1.40", "1.90", "2.40", "2.90"]),
            "fixed_fee": info["fixed_fee"],
            "settlement_delay_days": rng.choices([1, 2, 3], weights=[50, 35, 15])[0],
            "status": "ACTIVE",
            "onboarded_date": onboarded.isoformat(),
            "fee_effective_from": onboarded.isoformat(),
        })
        weights.append(min(rng.paretovariate(1.2), 40.0))  # a few big merchants, many small ones
    return merchants, weights


def make_orders(rng, count, merchants, weights, days, n_days):
    drafts = []
    for m in rng.choices(merchants, weights=weights, k=count):
        cur = m["settlement_currency"]
        amount = money(max(rng.lognormvariate(3.6, 0.9), 1.0) * config.CURRENCIES[cur]["amount_scale"], cur)
        last_day = n_days - m["settlement_delay_days"]   # so the capture can still settle inside the calendar
        drafts.append((rng.randint(0, last_day), rng.randint(0, 12 * 3600), m, amount))
    drafts.sort(key=lambda d: (d[0], d[1], d[2]["merchant_id"]))  # IDs follow time order
    orders = []
    for i, (day, second, m, amount) in enumerate(drafts, 1):
        created = datetime.combine(days[day], time(8)) + timedelta(seconds=second)
        orders.append({
            "payment_id": f"PAY-{Y}-{i:08d}", "merchant_id": m["merchant_id"],
            "customer_ref": f"CUST-{rng.randint(1, max(1, count // 2)):07d}",
            "amount": str(amount), "currency": m["settlement_currency"],
            "created_at": fmt_dt(created), "_day": day, "_dt": created,
            "_last_day": n_days - m["settlement_delay_days"],
        })
    return orders


def make_attempts_and_events(rng, orders, extra_attempts, days):
    attempts, events = [], []
    retried = set(rng.sample(range(len(orders)), extra_attempts))

    def add_event(order, attempt_id, event_type, amount, when, day):
        events.append({"event_id": f"EVT-{Y}-{len(events) + 1:08d}", "payment_id": order["payment_id"],
                       "attempt_id": attempt_id, "event_type": event_type, "amount": str(amount),
                       "currency": order["currency"], "event_at": fmt_dt(when), "_dt": when, "_day": day})
        return events[-1]

    for i, order in enumerate(orders):
        if i in retried:
            outcomes = ["DECLINED", "SUCCEEDED" if rng.random() < R["retry_success"] else "DECLINED"]
        else:
            r = rng.random()
            outcomes = ["SUCCEEDED" if r < R["single_attempt_success"] else ("DECLINED" if r < 0.99 else "ERROR")]
        method = rng.choice(PAYMENT_METHODS)
        amount = Decimal(order["amount"])
        t, capture = order["_dt"], None
        for n, outcome in enumerate(outcomes, 1):
            t += timedelta(seconds=rng.randint(2, 30) if n == 1 else rng.randint(60, 900))
            attempt_id = f"ATT-{order['payment_id']}-{n:02d}"
            if outcome == "SUCCEEDED":
                decline = ""
            elif outcome == "ERROR":
                decline = "PROCESSOR_TIMEOUT"
            else:
                decline = rng.choice(DECLINE_CODES[:-1])
            attempts.append({"attempt_id": attempt_id, "payment_id": order["payment_id"], "attempt_no": n,
                             "attempted_at": fmt_dt(t), "outcome": outcome, "decline_code": decline,
                             "payment_method": method})
            if outcome == "SUCCEEDED":
                auth_t = t + timedelta(seconds=rng.randint(1, 3))
                add_event(order, attempt_id, "AUTHORIZED", amount, auth_t, order["_day"])
                cap_t = auth_t + timedelta(seconds=rng.randint(5, 600))
                capture = add_event(order, attempt_id, "CAPTURED", amount, cap_t, order["_day"])
            else:
                add_event(order, attempt_id, "FAILED", amount, t + timedelta(seconds=rng.randint(1, 3)), order["_day"])

        if capture:  
            r = rng.random()
            refund = None
            if r < R["full_refund"]:
                refund = amount
            elif r < R["full_refund"] + R["partial_refund"]:
                refund = money(amount * Decimal(str(round(rng.uniform(0.1, 0.7), 4))), order["currency"])
                if refund <= 0 or refund >= amount:
                    refund = None
            if refund is not None:
                day = order["_day"] + rng.randint(1, config.MAX_REFUND_AFTER_DAYS)
                if day <= order["_last_day"]:
                    when = datetime.combine(days[day], time(9)) + timedelta(seconds=rng.randint(0, 9 * 3600))
                    add_event(order, capture["attempt_id"], "REFUNDED", refund, when, day)
    return attempts, events


def derive_order_fields(orders, attempts, events):
    """Order status and totals are DERIVED from events, never generated randomly."""
    ev_by_pay, att_count = defaultdict(list), defaultdict(int)
    for e in events:
        ev_by_pay[e["payment_id"]].append(e)
    for a in attempts:
        att_count[a["payment_id"]] += 1
    for o in orders:
        cur = o["currency"]
        captured = sum((Decimal(e["amount"]) for e in ev_by_pay[o["payment_id"]] if e["event_type"] == "CAPTURED"), Decimal(0))
        refunded = sum((Decimal(e["amount"]) for e in ev_by_pay[o["payment_id"]] if e["event_type"] == "REFUNDED"), Decimal(0))
        if captured == 0:
            status = "FAILED"
        elif refunded == 0:
            status = "CAPTURED"
        elif refunded >= captured:
            status = "REFUNDED"
        else:
            status = "PARTIALLY_REFUNDED"
        o.update({"status": status, "captured_amount": str(money(captured, cur)),
                  "refunded_amount": str(money(refunded, cur)), "attempt_count": att_count[o["payment_id"]]})


def make_webhook_rows(rng, events, n_ingest_twice, gt):
    """Turn logical events into ingested webhook rows (with natural duplicate webhooks)."""
    deliveries = []
    for e in events:
        received = e["_dt"] + timedelta(seconds=rng.randint(1, 20))
        row = {k: e[k] for k in ("event_id", "payment_id", "attempt_id", "event_type", "amount", "currency", "event_at")}
        deliveries.append(dict(row, received_at=fmt_dt(received), _rt=received))
        if rng.random() < R["duplicate_webhook"]:   # processor retried the webhook
            again = received + timedelta(seconds=rng.randint(30, 900))
            deliveries.append(dict(row, received_at=fmt_dt(again), _rt=again, _dup_webhook=True))
    deliveries.sort(key=lambda d: d["_rt"])
    for i, d in enumerate(deliveries, 1):
        d["delivery_id"] = f"WHK-{Y}-{i:08d}"

    # EDGE CASE: the same delivery is loaded twice by our own ingestion job
    candidates = [i for i, d in enumerate(deliveries) if not d.get("_dup_webhook")]
    twice = set(rng.sample(candidates, n_ingest_twice))
    rows = []
    for i, d in enumerate(deliveries):
        rows.append(d)
        if i in twice:
            rows.append(dict(d, _ingest_copy=True, _dup_webhook=False))
    for i, r in enumerate(rows, 1):
        r["ingest_id"] = f"ING-{Y}-{i:08d}"
        if r.get("_dup_webhook"):
            gt.add("SCENARIO", "DUPLICATE_WEBHOOK", "ProcessorEvent", r, "ingest_id", "DEDUPLICATED",
                   related=r["event_id"], note="processor re-sent the webhook with a new delivery_id")
        if r.get("_ingest_copy"):
            gt.add("ANOMALY", "DUPLICATE_INGESTION", "ProcessorEvent", r, "ingest_id", "DEDUPLICATED",
                   related=r["event_id"], note="same delivery_id loaded twice")
    return rows


def settlement_line(event, merchant):
    cur, amount = event["currency"], Decimal(event["amount"])
    if event["event_type"] == "CAPTURED":
        gross, line_type = amount, "CAPTURE"
        fee = money(amount * Decimal(merchant["fee_rate_pct"]) / 100 + Decimal(merchant["fixed_fee"]), cur)
    else:  # refunds are negative and fees are NOT returned
        gross, line_type, fee = -amount, "REFUND", money(0, cur)
    return {"event_id": event["event_id"], "payment_id": event["payment_id"], "line_type": line_type,
            "gross_amount": str(money(gross, cur)), "fee_amount": str(fee),
            "net_amount": str(money(gross - fee, cur)), "currency": cur,
            "event_date": event["_dt"].date().isoformat(), "_dt": event["_dt"]}


def finalize_batch(batch):
    """Assign line IDs and compute every batch total FROM its lines."""
    lines = sorted(batch["_lines"], key=lambda l: (l["_dt"], l["event_id"])) + batch["_dups"]
    if len(lines) > 999:
        raise ValueError("batch has more than 999 lines; increase settlement_days")
    cur = batch["currency"]
    for n, line in enumerate(lines, 1):
        line["settlement_line_id"] = f"STL-{batch['batch_id']}-{n:03d}"
        line["batch_id"] = batch["batch_id"]
    caps = [l for l in lines if l["line_type"] == "CAPTURE"]
    refs = [l for l in lines if l["line_type"] == "REFUND"]
    gross_c = sum((Decimal(l["gross_amount"]) for l in caps), Decimal(0))
    gross_r = -sum((Decimal(l["gross_amount"]) for l in refs), Decimal(0))
    fees = sum((Decimal(l["fee_amount"]) for l in lines), Decimal(0))
    batch.update({"line_count": len(lines), "capture_count": len(caps), "refund_count": len(refs),
                  "gross_captured": str(money(gross_c, cur)), "gross_refunded": str(money(gross_r, cur)),
                  "fee_total": str(money(fees, cur)), "net_amount": str(money(gross_c - gross_r - fees, cur)),
                  "status": "CLOSED"})
    batch["_final_lines"] = lines


def make_settlement(rng, events, orders, merchants, days, edges, gt):
    mer = {m["merchant_id"]: m for m in merchants}
    pay = {o["payment_id"]: o for o in orders}
    groups = defaultdict(list)
    for e in events:
        if e["event_type"] not in ("CAPTURED", "REFUNDED"):
            continue
        m = mer[pay[e["payment_id"]]["merchant_id"]]
        extra = rng.randint(1, config.MAX_EXTRA_SETTLEMENT_DELAY) if rng.random() < R["delayed_settlement"] else 0
        if e["_day"] + m["settlement_delay_days"] + extra > len(days) - 1:
            extra = 0   # cannot be late beyond the end of the calendar
        line = settlement_line(e, m)
        line["_delayed"] = extra > 0
        groups[(e["_day"] + m["settlement_delay_days"] + extra, e["currency"])].append(line)
        if extra:
            gt.add("SCENARIO", "DELAYED_SETTLEMENT", "ProcessorEvent", e, "event_id", "MATCHED",
                   note=f"settled {extra} business day(s) later than the merchant's normal delay")

    keys = sorted(groups, key=lambda k: (k[0], CURRENCY_CODES.index(k[1])))
    batches = []
    for i, (day, cur) in enumerate(keys, 1):
        batch = {"batch_id": f"SET-{Y}-{i:06d}", "currency": cur, "settlement_date": days[day].isoformat(),
                 "_lines": groups[(day, cur)], "_dups": []}
        for line in batch["_lines"]:
            line["batch_id"] = batch["batch_id"]
        batches.append(batch)
    by_id = {b["batch_id"]: b for b in batches}

    # EDGE CASES on settlement lines
    pool = [l for b in batches if len(b["_lines"]) >= 3 for l in b["_lines"]
            if l["line_type"] == "CAPTURE" and not l["_delayed"]]
    picked = rng.sample(pool, edges["missing_from_settlement"] + edges["duplicate_settlement_line"])
    missing = picked[:edges["missing_from_settlement"]]
    dups = picked[edges["missing_from_settlement"]:]
    for line in missing:   # processor never settled this captured event
        by_id[line["batch_id"]]["_lines"].remove(line)
        gt.add("ANOMALY", "MISSING_FROM_SETTLEMENT", "ProcessorEvent", line, "event_id",
               "EXCEPTION:MISSING_FROM_SETTLEMENT", related=line["batch_id"],
               note="captured event absent from every batch; a naive join would silently drop it")
    for line in dups:      # processor reported the same event twice
        copy = dict(line)
        by_id[line["batch_id"]]["_dups"].append(copy)
        gt.add("ANOMALY", "DUPLICATE_SETTLEMENT_LINE", "SettlementLine", copy, "settlement_line_id",
               "EXCEPTION:DUPLICATE_SETTLEMENT_LINE", related=line["event_id"])

    for b in batches:
        finalize_batch(b)
    lines = [l for b in batches for l in b["_final_lines"]]
    return batches, lines


def bank_line(value_date, amount, cur, counterparty, reference, description):
    return {"account_id": config.CURRENCIES[cur]["account_id"], "value_date": value_date.isoformat(),
            "amount": str(money(amount, cur)), "currency": cur,
            "direction": "CREDIT" if amount >= 0 else "DEBIT", "counterparty": counterparty,
            "reference": reference, "description": description}


def make_bank_lines(rng, batches, days, target, edges, gt):
    n_fee, n_mp, n_ccy = edges["bank_fee_difference"], edges["missing_payout"], edges["currency_mismatch"]
    special = rng.sample(batches, n_fee + n_mp + n_ccy)
    fee_ids = {b["batch_id"] for b in special[:n_fee]}
    mp_ids = {b["batch_id"] for b in special[n_fee:n_fee + n_mp]}
    ccy_ids = {b["batch_id"] for b in special[n_fee + n_mp:]}
    lines = []
    for b in batches:
        bid, cur = b["batch_id"], b["currency"]
        if bid in mp_ids:   # EDGE: payout never arrives
            gt.add("ANOMALY", "MISSING_PAYOUT", "SettlementBatch", b, "batch_id", "EXCEPTION:MISSING_PAYOUT",
                   note="closed batch with no bank credit")
            continue
        amount = Decimal(b["net_amount"])
        lag = rng.randint(0, 1)
        line_cur = cur
        ref = rng.choice([bid, f"PAYOUT {bid}", f"NOVAPAY STLMT {bid} {cur}"])
        if bid in fee_ids:      # EDGE: fees were not deducted on the bank side
            amount += Decimal(b["fee_total"])
            kind = ("FEE_DIFFERENCE", "EXCEPTION:FEE_DIFFERENCE")
        elif bid in ccy_ids:    # EDGE: paid in the wrong currency
            line_cur = rng.choice([c for c in CURRENCY_CODES if c != cur])
            kind = ("CURRENCY_MISMATCH", "EXCEPTION:CURRENCY_MISMATCH")
        else:
            kind = None
            if rng.random() < R["rounding_difference"]:
                amount += minor_unit(cur) * rng.choice([-1, 1])
                gt.add("SCENARIO", "ROUNDING_DIFFERENCE", "SettlementBatch", b, "batch_id",
                       "MATCHED_WITH_TOLERANCE", note="bank amount differs by one minor unit")
            if rng.random() < R["delayed_payout"]:
                lag = rng.randint(2, 4)
                gt.add("SCENARIO", "DELAYED_PAYOUT", "SettlementBatch", b, "batch_id", "MATCHED",
                       note=f"bank credit {lag} days after settlement")
        settle = date.fromisoformat(b["settlement_date"])
        line = bank_line(settle + timedelta(days=lag), amount, line_cur, config.PROCESSOR_NAME, ref,
                         "Card settlement payout")
        lines.append(line)
        if kind:
            gt.add("ANOMALY", kind[0], "BankStatementLine", line, "bank_line_id", kind[1], related=bid)

    for _ in range(edges["unmatched_bank_line"]):  # EDGE: processor credit with no batch behind it
        cur = rng.choices(CURRENCY_CODES, weights=CURRENCY_WEIGHTS)[0]
        amount = Decimal(str(rng.uniform(100, 3000))) * Decimal(str(config.CURRENCIES[cur]["amount_scale"]))
        line = bank_line(days[rng.randint(1, len(days) - 1)], amount, cur, config.PROCESSOR_NAME,
                         rng.choice(["", "PAYOUT ADJ", "STLMT CORRECTION"]), "Card settlement payout")
        lines.append(line)
        gt.add("ANOMALY", "UNMATCHED_BANK_LINE", "BankStatementLine", line, "bank_line_id",
               "EXCEPTION:UNMATCHED_BANK_LINE", note="processor credit with no reference and no batch")

    filler = target - len(lines)
    if filler < 0:
        raise ValueError("bank_lines target is smaller than the number of payouts")
    span = (days[-1] - days[0]).days + 4
    for _ in range(filler):  # normal non-processor activity (kept, marked OUT_OF_SCOPE later)
        desc, cp, sign, lo, hi, prefix = rng.choice(OTHER_BANK_ACTIVITY)
        cur = rng.choices(CURRENCY_CODES, weights=CURRENCY_WEIGHTS)[0]
        amount = sign * Decimal(str(rng.uniform(lo, hi))) * Decimal(str(config.CURRENCIES[cur]["amount_scale"]))
        lines.append(bank_line(days[0] + timedelta(days=rng.randint(0, span)), amount, cur, cp,
                               f"{prefix}-{rng.randint(100000, 999999)}", desc))

    lines.sort(key=lambda l: l["value_date"])  # stable sort keeps it deterministic
    for i, line in enumerate(lines, 1):
        line["bank_line_id"] = f"BANK-{Y}-{i:06d}"
    return lines


def generate(scale="starter", seed=config.DEFAULT_SEED, out_dir=None, quiet=False):
    p, edges = config.SCALES[scale], config.EDGE_CASES[scale]
    out_dir = out_dir or os.path.join("output", scale)
    rng = random.Random(seed)
    gt = GroundTruth()

    n_days = p["settlement_days"]
    days = business_days(config.CALENDAR_START, n_days + 1)          # index 0 .. n_days

    merchants, weights = make_merchants(rng, p["merchants"])
    orders = make_orders(rng, p["orders"], merchants, weights, days, n_days)
    attempts, events = make_attempts_and_events(rng, orders, p["extra_attempts"], days)

    # EDGE: refund timestamp earlier than its capture
    captures = {e["payment_id"]: e for e in events if e["event_type"] == "CAPTURED"}
    refunds = [e for e in events if e["event_type"] == "REFUNDED"]
    for r in rng.sample(refunds, edges["refund_before_capture"]):
        cap = captures[r["payment_id"]]
        r["_dt"] = cap["_dt"] - timedelta(minutes=rng.randint(1, 60))
        r["_day"] = cap["_day"]
        r["event_at"] = fmt_dt(r["_dt"])
        gt.add("ANOMALY", "REFUND_BEFORE_CAPTURE", "ProcessorEvent", r, "event_id",
               "EXCEPTION:REFUND_BEFORE_CAPTURE", related=cap["event_id"])

    derive_order_fields(orders, attempts, events)
    webhook_rows = make_webhook_rows(rng, events, edges["duplicate_ingestion"], gt)
    batches, lines = make_settlement(rng, events, orders, merchants, days, edges, gt)
    bank = make_bank_lines(rng, batches, days, p["bank_lines"], edges, gt)

    data_dir = os.path.join(out_dir, "data")
    tables = {"merchants": merchants, "payment_orders": orders, "payment_attempts": attempts,
              "processor_events": webhook_rows, "settlement_batches": batches,
              "settlement_lines": lines, "bank_statement_lines": bank}
    for name, rows in tables.items():
        save_table(data_dir, name, rows)

    gt_rows = gt.rows()
    gt_cols = ["case_id", "category", "issue_type", "spec_edge_case", "entity_type", "entity_id",
               "related_id", "expected_decision", "note"]
    gt_dir = os.path.join(out_dir, "ground_truth")
    write_csv(os.path.join(gt_dir, "ground_truth.csv"), gt_rows, gt_cols)
    write_json(os.path.join(gt_dir, "ground_truth.json"), [{c: r[c] for c in gt_cols} for r in gt_rows])

    files = []
    for folder in (data_dir, os.path.join(data_dir, "json"), gt_dir):
        for fn in sorted(os.listdir(folder)):
            path = os.path.join(folder, fn)
            if os.path.isfile(path):
                rows = sum(1 for _ in open(path, encoding="utf-8")) - 1 if fn.endswith(".csv") else None
                files.append({"path": os.path.relpath(path, out_dir), "rows": rows, "sha256": sha256_file(path)})
    manifest = {
        "generator": "generate_data.py", "generator_version": config.GENERATOR_VERSION,
        "command": f"python generate_data.py --scale {scale} --seed {seed}",
        "seed": seed, "scale": scale, "parameters": p, "edge_cases": edges, "rates": R,
        "python_version": platform.python_version(),
        "provenance": {"external_data_sources": [],
                       "statement": ("100% synthetic. Names come from built-in word lists; no real people, "
                                     "cards, merchants or bank data were used or downloaded."),
                       "license": "Generated data may be freely redistributed."},
        "row_counts": {name: len(rows) for name, rows in tables.items()} | {"ground_truth": len(gt_rows)},
        "files": files,
    }
    write_json(os.path.join(out_dir, "manifest.json"), manifest)
    if not quiet:
        print(f"[generate] {scale} seed={seed} -> {out_dir}")
        for k, v in manifest["row_counts"].items():
            print(f"    {k:<22}{v:>8,}")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate synthetic payment reconciliation data")
    ap.add_argument("--scale", choices=list(config.SCALES), default="starter")
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    generate(a.scale, a.seed, a.out)
