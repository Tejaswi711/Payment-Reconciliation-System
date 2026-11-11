## Evaluation Results

**Overall Acceptance: PASS**

### 1. Ground Truth Evaluation

| Metric | Result |
|---|---:|
| Anomaly cases | 18 |
| Anomaly cases handled | 18 |
| Anomaly recall | 1.0 (100%) |
| Scenario cases | 157 |
| Scenario accuracy | 1.0 (100%) |
| Exception precision | 1.0 (100%) |
| Exception recall | 1.0 (100%) |
| Exception F1-score | 1.0 (100%) |
| False-positive exceptions | 0 |

### 2. Acceptance Criteria

| Criterion | Status | Result |
|---|---|---|
| Matched amounts reconcile within configured tolerance | PASS | 2,507 matched decisions; 0 outside tolerance |
| Every unmatched item is recorded as an exception | PASS | 0 unmatched decisions without an exception |
| Duplicate events are idempotent | PASS | 74 duplicate rows ignored |
| Fee and refund treatment is consistent | PASS | 0 line fee/sign errors, 0 batch net errors, 0 over-refunded orders |

### 3. Evaluation by Issue Type

| Issue Type | Category | Expected | Handled | Recall |
|---|---|---:|---:|---:|
| CURRENCY_MISMATCH | ANOMALY | 2 | 2 | 1.0 |
| DELAYED_PAYOUT | SCENARIO | 9 | 9 | 1.0 |
| DELAYED_SETTLEMENT | SCENARIO | 74 | 74 | 1.0 |
| DUPLICATE_INGESTION | ANOMALY | 4 | 4 | 1.0 |
| DUPLICATE_SETTLEMENT_LINE | ANOMALY | 3 | 3 | 1.0 |
| DUPLICATE_WEBHOOK | SCENARIO | 70 | 70 | 1.0 |
| FEE_DIFFERENCE | ANOMALY | 2 | 2 | 1.0 |
| MISSING_FROM_SETTLEMENT | ANOMALY | 2 | 2 | 1.0 |
| MISSING_PAYOUT | ANOMALY | 1 | 1 | 1.0 |
| REFUND_BEFORE_CAPTURE | ANOMALY | 3 | 3 | 1.0 |
| ROUNDING_DIFFERENCE | SCENARIO | 4 | 4 | 1.0 |
| UNMATCHED_BANK_LINE | ANOMALY | 1 | 1 | 1.0 |

### 4. Exception Evaluation

| Exception Type | Raised | True Positives | Precision |
|---|---:|---:|---:|
| CURRENCY_MISMATCH | 2 | 2 | 1.0 |
| DUPLICATE_SETTLEMENT_LINE | 3 | 3 | 1.0 |
| FEE_DIFFERENCE | 2 | 2 | 1.0 |
| MISSING_FROM_SETTLEMENT | 2 | 2 | 1.0 |
| MISSING_PAYOUT | 1 | 1 | 1.0 |
| REFUND_BEFORE_CAPTURE | 3 | 3 | 1.0 |
| UNMATCHED_BANK_LINE | 1 | 1 | 1.0 |

### 5. Key Results

- All 18 labelled anomaly cases were handled.
- All 157 scenario cases were handled correctly.
- No false-positive exceptions were recorded.
- Duplicate event ingestion was handled idempotently.
- No unmatched decisions were silently dropped.
- Fee adjustments and refund handling passed the acceptance checks.

**Final Evaluation Status: PASS**