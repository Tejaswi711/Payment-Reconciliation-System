import os

import config

Y = config.ID_YEAR
CURRENCIES = list(config.CURRENCIES)
COUNTRIES = sorted({c for info in config.CURRENCIES.values() for c in info["countries"]})
ACCOUNTS = [info["account_id"] for info in config.CURRENCIES.values()]

CATEGORIES = ["RETAIL", "DIGITAL_GOODS", "TRAVEL", "FOOD_DELIVERY", "SUBSCRIPTIONS", "ELECTRONICS"]
DECLINE_CODES = ["INSUFFICIENT_FUNDS", "DO_NOT_HONOR", "EXPIRED_CARD", "SUSPECTED_FRAUD",
                 "INVALID_CVV", "PROCESSOR_TIMEOUT"]
PAYMENT_METHODS = ["CARD_VISA", "CARD_MASTERCARD", "CARD_AMEX"]
EXCEPTION_TYPES = ["MISSING_FROM_SETTLEMENT", "DUPLICATE_SETTLEMENT_LINE", "ORPHAN_SETTLEMENT_LINE",
                   "LINE_AMOUNT_MISMATCH", "LINE_CURRENCY_MISMATCH", "LATE_SETTLEMENT",
                   "REFUND_BEFORE_CAPTURE", "EVENT_PAYLOAD_CONFLICT", "FEE_DIFFERENCE",
                   "AMOUNT_MISMATCH", "CURRENCY_MISMATCH", "DATE_OUT_OF_WINDOW",
                   "DUPLICATE_PAYOUT", "UNMATCHED_BANK_LINE", "AMBIGUOUS_BANK_MATCH", "MISSING_PAYOUT"]
ROLES = ["operations_analyst", "risk_compliance_reviewer", "system_administrator"]
STATUSES_AFTER_ACTION = ["RESOLVED", "PENDING_PROCESSOR", "IN_REVIEW", "ESCALATED",
                         "UNDER_COMPLIANCE_REVIEW"]
ACTIONS = ["POST_FEE_ADJUSTMENT", "RAISE_PROCESSOR_CLAIM", "CHASE_PAYOUT", "INVESTIGATE",
           "ESCALATE", "COMPLIANCE_REVIEW"]

MONEY = "Decimal string rounded to currency minor unit (2 dp, JPY 0 dp)"


def col(name, type_, description, required=True, enum=None, pattern=None, fk=None,
        enforced_fk=True, unique=False, unit="", rule=""):
    return {"name": name, "type": type_, "description": description, "required": required,
            "enum": enum, "pattern": pattern, "fk": fk, "enforced_fk": enforced_fk,
            "unique": unique, "unit": unit, "rule": rule}


TABLES = {
    # ------------------------------ INPUT DATA ------------------------------
    "merchants": {
        "entity": "Merchant", "folder": "data", "pk": "merchant_id",
        "description": "Customer / account holder that sells goods and receives settled funds.",
        "lifecycle": "ACTIVE -> SUSPENDED -> CLOSED (generated merchants are ACTIVE)",
        "columns": [
            col("merchant_id", "TEXT", "Primary key", pattern=r"^MER-\d{6}$", unique=True),
            col("merchant_name", "TEXT", "Synthetic trading name from word lists"),
            col("country", "TEXT", "ISO-3166 alpha-2 country", enum=COUNTRIES),
            col("settlement_currency", "TEXT", "ISO-4217 currency the merchant sells in", enum=CURRENCIES),
            col("category", "TEXT", "Business category", enum=CATEGORIES),
            col("fee_rate_pct", "DECIMAL", "Percentage fee on each capture", unit="percent", rule="0 < x < 5"),
            col("fixed_fee", "DECIMAL", "Fixed fee on each capture", unit="currency", rule=MONEY),
            col("settlement_delay_days", "INTEGER", "Business days from capture to settlement",
                enum=["1", "2", "3"], unit="business days"),
            col("status", "TEXT", "Lifecycle state", enum=["ACTIVE", "SUSPENDED", "CLOSED"]),
            col("onboarded_date", "DATE", "Date onboarded", rule="ISO date"),
            col("fee_effective_from", "DATE", "Effective date of fee plan", rule=">= onboarded_date"),
        ]},
    "payment_orders": {
        "entity": "PaymentOrder", "folder": "data", "pk": "payment_id",
        "description": "A customer's request to pay a merchant. Status is DERIVED from processor events.",
        "lifecycle": "CREATED -> CAPTURED -> PARTIALLY_REFUNDED / REFUNDED, or CREATED -> FAILED",
        "columns": [
            col("payment_id", "TEXT", "Primary key", pattern=rf"^PAY-{Y}-\d{{8}}$", unique=True),
            col("merchant_id", "TEXT", "FK to merchant", fk="merchants.merchant_id"),
            col("customer_ref", "TEXT", "Synthetic customer reference (no personal data)", pattern=r"^CUST-\d{7}$"),
            col("amount", "DECIMAL", "Order amount", unit="currency", rule=MONEY + "; > 0"),
            col("currency", "TEXT", "Currency = merchant settlement currency", enum=CURRENCIES),
            col("created_at", "DATETIME", "Order creation time", rule="ISO datetime"),
            col("status", "TEXT", "Derived status", enum=["CAPTURED", "PARTIALLY_REFUNDED", "REFUNDED", "FAILED"]),
            col("captured_amount", "DECIMAL", "Derived: sum of CAPTURED events", unit="currency"),
            col("refunded_amount", "DECIMAL", "Derived: sum of REFUNDED events", unit="currency",
                rule="<= captured_amount"),
            col("attempt_count", "INTEGER", "Derived: number of attempts", rule="1 or 2"),
        ]},
    "payment_attempts": {
        "entity": "PaymentAttempt", "folder": "data", "pk": "attempt_id",
        "description": "One authorisation try for an order. A declined first try may be retried.",
        "lifecycle": "SUCCEEDED / DECLINED / ERROR (terminal)",
        "columns": [
            col("attempt_id", "TEXT", "Primary key ATT-<payment-id>-NN",
                pattern=rf"^ATT-PAY-{Y}-\d{{8}}-\d{{2}}$", unique=True),
            col("payment_id", "TEXT", "FK to order", fk="payment_orders.payment_id"),
            col("attempt_no", "INTEGER", "1, 2 ... in time order"),
            col("attempted_at", "DATETIME", "Attempt time", rule=">= order created_at"),
            col("outcome", "TEXT", "Result", enum=["SUCCEEDED", "DECLINED", "ERROR"]),
            col("decline_code", "TEXT", "Reason when not successful", required=False, enum=DECLINE_CODES),
            col("payment_method", "TEXT", "Card scheme", enum=PAYMENT_METHODS),
        ]},
    "processor_events": {
        "entity": "ProcessorEvent", "folder": "data", "pk": "ingest_id",
        "description": ("Every webhook row exactly as ingested. event_id is the processor's logical key and "
                        "can repeat (duplicate webhook / duplicate ingestion) -> must be deduplicated."),
        "lifecycle": "AUTHORIZED -> CAPTURED -> REFUNDED, or FAILED",
        "columns": [
            col("ingest_id", "TEXT", "Primary key, one per ingested row", pattern=rf"^ING-{Y}-\d{{8}}$", unique=True),
            col("delivery_id", "TEXT", "Webhook delivery id (repeats if same delivery ingested twice)",
                pattern=rf"^WHK-{Y}-\d{{8}}$"),
            col("event_id", "TEXT", "Logical event id (idempotency key)", pattern=rf"^EVT-{Y}-\d{{8}}$"),
            col("payment_id", "TEXT", "FK to order", fk="payment_orders.payment_id"),
            col("attempt_id", "TEXT", "FK to attempt", fk="payment_attempts.attempt_id"),
            col("event_type", "TEXT", "Event type", enum=["AUTHORIZED", "CAPTURED", "REFUNDED", "FAILED"]),
            col("amount", "DECIMAL", "Event amount (positive)", unit="currency", rule=MONEY),
            col("currency", "TEXT", "Currency", enum=CURRENCIES),
            col("event_at", "DATETIME", "When it happened at the processor"),
            col("received_at", "DATETIME", "When our webhook endpoint received it", rule=">= event_at"),
        ]},
    "settlement_batches": {
        "entity": "SettlementBatch", "folder": "data", "pk": "batch_id",
        "description": "Processor batch per settlement date and currency. All totals derived from its lines.",
        "lifecycle": "OPEN -> CLOSED (all generated batches are CLOSED)",
        "columns": [
            col("batch_id", "TEXT", "Primary key", pattern=rf"^SET-{Y}-\d{{6}}$", unique=True),
            col("currency", "TEXT", "Batch currency", enum=CURRENCIES),
            col("settlement_date", "DATE", "Business day the batch settled"),
            col("line_count", "INTEGER", "Derived: number of lines"),
            col("capture_count", "INTEGER", "Derived: CAPTURE lines"),
            col("refund_count", "INTEGER", "Derived: REFUND lines"),
            col("gross_captured", "DECIMAL", "Derived: sum of capture gross", unit="currency"),
            col("gross_refunded", "DECIMAL", "Derived: sum of refund gross (positive)", unit="currency"),
            col("fee_total", "DECIMAL", "Derived: sum of line fees", unit="currency"),
            col("net_amount", "DECIMAL", "Derived: gross_captured - gross_refunded - fee_total", unit="currency"),
            col("status", "TEXT", "Lifecycle state", enum=["OPEN", "CLOSED"]),
        ]},
    "settlement_lines": {
        "entity": "SettlementLine", "folder": "data", "pk": "settlement_line_id",
        "description": "One captured or refunded event inside a batch. Refunds are negative, fees not returned.",
        "lifecycle": "immutable",
        "columns": [
            col("settlement_line_id", "TEXT", "Primary key STL-<batch-id>-NNN",
                pattern=rf"^STL-SET-{Y}-\d{{6}}-\d{{3}}$", unique=True),
            col("batch_id", "TEXT", "FK to batch", fk="settlement_batches.batch_id"),
            col("event_id", "TEXT", "Logical FK to processor event", fk="processor_events.event_id",
                enforced_fk=False),
            col("payment_id", "TEXT", "FK to order", fk="payment_orders.payment_id"),
            col("line_type", "TEXT", "Line type", enum=["CAPTURE", "REFUND"]),
            col("gross_amount", "DECIMAL", "Signed amount (+capture, -refund)", unit="currency"),
            col("fee_amount", "DECIMAL", "round(gross*rate%+fixed) for CAPTURE, 0 for REFUND", unit="currency"),
            col("net_amount", "DECIMAL", "gross_amount - fee_amount", unit="currency"),
            col("currency", "TEXT", "Currency = batch currency", enum=CURRENCIES),
            col("event_date", "DATE", "Date of the processor event", rule="<= batch settlement_date"),
        ]},
    "bank_statement_lines": {
        "entity": "BankStatementLine", "folder": "data", "pk": "bank_line_id",
        "description": ("Lines on the platform's bank statement. Processor payouts are in scope; other "
                        "activity (rent, payroll...) is kept and marked OUT_OF_SCOPE, never dropped."),
        "lifecycle": "immutable",
        "columns": [
            col("bank_line_id", "TEXT", "Primary key", pattern=rf"^BANK-{Y}-\d{{6}}$", unique=True),
            col("account_id", "TEXT", "Bank account (one per currency)", enum=ACCOUNTS),
            col("value_date", "DATE", "Value date"),
            col("amount", "DECIMAL", "Signed amount, credit positive", unit="currency"),
            col("currency", "TEXT", "Line currency", enum=CURRENCIES),
            col("direction", "TEXT", "CREDIT if amount >= 0", enum=["CREDIT", "DEBIT"]),
            col("counterparty", "TEXT", "Counterparty name"),
            col("reference", "TEXT", "Free-text reference (normally contains SET id)", required=False),
            col("description", "TEXT", "Bank narrative"),
        ]},

    # ------------------------------ OUTPUTS ------------------------------
    "event_dedup_log": {
        "entity": "EventDedupLog", "folder": "recon", "pk": "dedup_id",
        "description": "Every duplicate event row that was ignored (proves idempotent ingestion).",
        "lifecycle": "append-only",
        "columns": [
            col("dedup_id", "TEXT", "Primary key", pattern=rf"^DUP-{Y}-\d{{6}}$", unique=True),
            col("ingest_id", "TEXT", "Ignored row", fk="processor_events.ingest_id"),
            col("event_id", "TEXT", "Logical event id"),
            col("duplicate_of_ingest_id", "TEXT", "Row that was kept", fk="processor_events.ingest_id"),
            col("reason", "TEXT", "Why it is a duplicate", enum=["DUPLICATE_WEBHOOK", "DUPLICATE_INGESTION"]),
            col("payload_identical", "TEXT", "Y if payload equals kept row", enum=["Y", "N"]),
            col("decision", "TEXT", "Decision", enum=["IGNORED_IDEMPOTENT"]),
        ]},
    "reconciliation_matches": {
        "entity": "ReconciliationMatch", "folder": "recon", "pk": "match_id",
        "description": ("Bridge table. One row per decision at two levels: EVENT_TO_SETTLEMENT "
                        "(event <-> settlement line) and BATCH_TO_BANK (batch <-> bank line)."),
        "lifecycle": "immutable decision record",
        "columns": [
            col("match_id", "TEXT", "Primary key", pattern=rf"^REC-{Y}-\d{{6}}$", unique=True),
            col("match_level", "TEXT", "Level", enum=["EVENT_TO_SETTLEMENT", "BATCH_TO_BANK"]),
            col("event_id", "TEXT", "Processor event", required=False),
            col("settlement_line_id", "TEXT", "Settlement line", required=False,
                fk="settlement_lines.settlement_line_id"),
            col("batch_id", "TEXT", "Batch", required=False, fk="settlement_batches.batch_id"),
            col("bank_line_id", "TEXT", "Bank line", required=False, fk="bank_statement_lines.bank_line_id"),
            col("match_status", "TEXT", "Outcome", enum=["MATCHED", "MATCHED_WITH_TOLERANCE", "PARTIAL",
                                                          "UNMATCHED", "DUPLICATE", "OUT_OF_SCOPE"]),
            col("match_method", "TEXT", "Rule used", enum=["EVENT_ID", "REFERENCE", "AMOUNT_CURRENCY_DATE",
                                                           "COUNTERPARTY_FILTER", "NONE"]),
            col("expected_amount", "DECIMAL", "Amount expected", required=False, unit="currency"),
            col("actual_amount", "DECIMAL", "Amount found", required=False, unit="currency"),
            col("difference", "DECIMAL", "actual - expected", required=False, unit="currency"),
            col("currency", "TEXT", "Currency of expected amount", required=False, enum=CURRENCIES),
            col("tolerance", "DECIMAL", "Configured tolerance", required=False, unit="currency"),
            col("matched_on", "DATE", "Run date"),
        ]},
    "exceptions": {
        "entity": "Exception", "folder": "recon", "pk": "exception_id",
        "description": "Every unmatched / partial / suspicious item. Status at creation is OPEN; changes go to resolutions.",
        "lifecycle": "OPEN -> (see resolutions) RESOLVED / PENDING_PROCESSOR / IN_REVIEW / ESCALATED / UNDER_COMPLIANCE_REVIEW",
        "columns": [
            col("exception_id", "TEXT", "Primary key", pattern=rf"^EXC-{Y}-\d{{6}}$", unique=True),
            col("exception_type", "TEXT", "Rule that fired", enum=EXCEPTION_TYPES),
            col("severity", "TEXT", "Severity", enum=["LOW", "MEDIUM", "HIGH"]),
            col("entity_type", "TEXT", "Type of flagged record",
                enum=["ProcessorEvent", "SettlementLine", "SettlementBatch", "BankStatementLine"]),
            col("entity_id", "TEXT", "ID of flagged record"),
            col("related_ids", "TEXT", "Other IDs for traceability (; separated)", required=False),
            col("match_id", "TEXT", "Decision row", required=False, fk="reconciliation_matches.match_id"),
            col("amount_difference", "DECIMAL", "Money at stake", required=False, unit="currency"),
            col("currency", "TEXT", "Currency", required=False, enum=CURRENCIES),
            col("rule", "TEXT", "Plain-English rule"),
            col("status", "TEXT", "Status at creation", enum=["OPEN"]),
            col("created_at", "DATETIME", "Run timestamp"),
        ]},
    "resolutions": {
        "entity": "Resolution", "folder": "recon", "pk": "resolution_id",
        "description": "Append-only history of actions taken on exceptions (latest step = current status).",
        "lifecycle": "append-only",
        "columns": [
            col("resolution_id", "TEXT", "Primary key", pattern=rf"^RES-{Y}-\d{{6}}$", unique=True),
            col("exception_id", "TEXT", "FK to exception", fk="exceptions.exception_id"),
            col("step_no", "INTEGER", "1, 2 ... per exception"),
            col("actor_role", "TEXT", "Who acted", enum=ROLES),
            col("action", "TEXT", "Action", enum=ACTIONS),
            col("resulting_status", "TEXT", "Status after action", enum=STATUSES_AFTER_ACTION),
            col("recorded_at", "DATETIME", "When recorded"),
            col("note", "TEXT", "Explanation"),
        ]},
}

INPUT_TABLES = [n for n, t in TABLES.items() if t["folder"] == "data"]
OUTPUT_TABLES = [n for n, t in TABLES.items() if t["folder"] == "recon"]

RELATIONSHIPS = [
    ("Merchant", "PaymentOrder", "1:N", "payment_orders.merchant_id", "required"),
    ("PaymentOrder", "PaymentAttempt", "1:N (1-2)", "payment_attempts.payment_id", "required"),
    ("PaymentAttempt", "ProcessorEvent", "1:N", "processor_events.attempt_id", "required"),
    ("PaymentOrder", "ProcessorEvent", "1:N", "processor_events.payment_id", "required"),
    ("ProcessorEvent (event_id)", "ingested rows", "1:N", "processor_events.event_id",
     "duplicates allowed in input, removed idempotently"),
    ("SettlementBatch", "SettlementLine", "1:N", "settlement_lines.batch_id", "required"),
    ("ProcessorEvent", "SettlementLine", "1:0..1 expected", "settlement_lines.event_id",
     "0 or >1 raises an exception"),
    ("ProcessorEvent", "SettlementLine", "N:M bridge", "reconciliation_matches (EVENT_TO_SETTLEMENT)", "bridge"),
    ("SettlementBatch", "BankStatementLine", "N:M bridge", "reconciliation_matches (BATCH_TO_BANK)", "bridge"),
    ("ReconciliationMatch", "Exception", "1:0..N", "exceptions.match_id", "optional"),
    ("Exception", "Resolution", "1:N", "resolutions.exception_id", "append-only history"),
    ("ProcessorEvent row", "EventDedupLog", "1:0..1", "event_dedup_log.ingest_id", "only duplicates logged"),
]

SQL_TYPES = {"TEXT": "TEXT", "INTEGER": "INTEGER", "DECIMAL": "NUMERIC(18,2)",
             "DATE": "TEXT", "DATETIME": "TEXT"}

VIEWS_SQL = """
-- Current status of each exception = its latest resolution step (history is never overwritten)
CREATE VIEW exception_current_status AS
SELECT e.exception_id, e.exception_type, e.severity, e.entity_type, e.entity_id,
       r.resulting_status AS current_status, r.actor_role AS last_actor
FROM exceptions e
LEFT JOIN resolutions r
  ON r.exception_id = e.exception_id
 AND r.step_no = (SELECT MAX(step_no) FROM resolutions r2 WHERE r2.exception_id = e.exception_id);

-- Processor events after idempotent deduplication
CREATE VIEW processor_events_unique AS
SELECT * FROM processor_events
WHERE ingest_id NOT IN (SELECT ingest_id FROM event_dedup_log);
"""


def create_table_sql(name):
    t = TABLES[name]
    parts = []
    for c in t["columns"]:
        line = f"  {c['name']} {SQL_TYPES[c['type']]}"
        if c["required"]:
            line += " NOT NULL"
        if c["enum"] and c["type"] == "TEXT":
            values = ", ".join(f"'{v}'" for v in c["enum"])
            line += f" CHECK ({c['name']} IN ({values}))"
        parts.append(line)
    parts.append(f"  PRIMARY KEY ({t['pk']})")
    for c in t["columns"]:
        if c["fk"] and c["enforced_fk"]:
            ref_table, ref_col = c["fk"].split(".")
            parts.append(f"  FOREIGN KEY ({c['name']}) REFERENCES {ref_table}({ref_col})")
    return f"CREATE TABLE {name} (\n" + ",\n".join(parts) + "\n);\n"


def schema_sql():
    out = ["-- Generated by schema.py. SQLite / PostgreSQL compatible.\n"]
    out += [create_table_sql(n) for n in TABLES]
    out.append(VIEWS_SQL)
    return "\n".join(out)


def data_dictionary_md():
    lines = ["# Data dictionary", "",
             "Generated from `schema.py` (single source of truth). Money is stored as a decimal string "
             "rounded to the currency minor unit with ROUND_HALF_UP (JPY has 0 decimals).", ""]
    for name, t in TABLES.items():
        lines += [f"## {t['entity']} (`{t['folder']}/{name}.csv`)", "", t["description"], "",
                  f"* Primary key: `{t['pk']}`", f"* Lifecycle: {t['lifecycle']}", "",
                  "| Field | Type | Required | Allowed values / pattern | Unit | Unique | FK | Rule | Description |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for c in t["columns"]:
            allowed = ", ".join(c["enum"]) if c["enum"] else (f"`{c['pattern']}`" if c["pattern"] else "")
            fk = (c["fk"] or "") + ("" if c["enforced_fk"] or not c["fk"] else " (logical)")
            lines.append(f"| {c['name']} | {c['type']} | {'yes' if c['required'] else 'no'} | {allowed} | "
                         f"{c['unit']} | {'yes' if c['unique'] else ''} | {fk} | {c['rule']} | {c['description']} |")
        lines.append("")
    lines += ["## Relationships", "", "| Parent | Child | Cardinality | Key | Notes |", "|---|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | `{k}` | {n} |" for a, b, c, k, n in RELATIONSHIPS]
    lines += ["", "## Ground truth (`ground_truth/ground_truth.csv`, never read by the reconciler)", "",
              "| Field | Description |", "|---|---|",
              "| case_id | GT-NNNNNN |", "| category | ANOMALY (injected edge case) or SCENARIO (normal but tricky) |",
              "| issue_type | e.g. DUPLICATE_SETTLEMENT_LINE |",
              "| spec_edge_case | The edge case wording from the problem statement |",
              "| entity_type / entity_id | Record the label applies to |",
              "| related_id | Linked record for traceability |",
              "| expected_decision | EXCEPTION:<TYPE>, DEDUPLICATED, MATCHED or MATCHED_WITH_TOLERANCE |",
              "| note | Human explanation |", ""]
    return "\n".join(lines)


def write_docs(root="."):
    os.makedirs(os.path.join(root, "docs"), exist_ok=True)
    os.makedirs(os.path.join(root, "sql"), exist_ok=True)
    with open(os.path.join(root, "docs", "data_dictionary.md"), "w", encoding="utf-8") as f:
        f.write(data_dictionary_md())
    with open(os.path.join(root, "sql", "schema.sql"), "w", encoding="utf-8") as f:
        f.write(schema_sql())


if __name__ == "__main__":
    write_docs()
    print("Wrote docs/data_dictionary.md and sql/schema.sql")
