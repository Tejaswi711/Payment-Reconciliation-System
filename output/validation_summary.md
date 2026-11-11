# Validation summary

Scale: **starter**, overall: **PASS**

| Check | Category | Status | Rows | Failures | Labelled |
|---|---|---|---|---|---|
| merchants: primary key merchant_id unique | primary_key | PASS | 100 | 0 | 0 |
| merchants.merchant_id required | required | PASS | 100 | 0 | 0 |
| merchants.merchant_id ID format | id_format | PASS | 100 | 0 | 0 |
| merchants.merchant_name required | required | PASS | 100 | 0 | 0 |
| merchants.country required | required | PASS | 100 | 0 | 0 |
| merchants.country allowed values | enum | PASS | 100 | 0 | 0 |
| merchants.settlement_currency required | required | PASS | 100 | 0 | 0 |
| merchants.settlement_currency allowed values | enum | PASS | 100 | 0 | 0 |
| merchants.category required | required | PASS | 100 | 0 | 0 |
| merchants.category allowed values | enum | PASS | 100 | 0 | 0 |
| merchants.fee_rate_pct required | required | PASS | 100 | 0 | 0 |
| merchants.fixed_fee required | required | PASS | 100 | 0 | 0 |
| merchants.settlement_delay_days required | required | PASS | 100 | 0 | 0 |
| merchants.settlement_delay_days allowed values | enum | PASS | 100 | 0 | 0 |
| merchants.status required | required | PASS | 100 | 0 | 0 |
| merchants.status allowed values | enum | PASS | 100 | 0 | 0 |
| merchants.onboarded_date required | required | PASS | 100 | 0 | 0 |
| merchants.fee_effective_from required | required | PASS | 100 | 0 | 0 |
| payment_orders: primary key payment_id unique | primary_key | PASS | 2500 | 0 | 0 |
| payment_orders.payment_id required | required | PASS | 2500 | 0 | 0 |
| payment_orders.payment_id ID format | id_format | PASS | 2500 | 0 | 0 |
| payment_orders.merchant_id required | required | PASS | 2500 | 0 | 0 |
| payment_orders.merchant_id -> merchants.merchant_id | foreign_key | PASS | 2500 | 0 | 0 |
| payment_orders.customer_ref required | required | PASS | 2500 | 0 | 0 |
| payment_orders.customer_ref ID format | id_format | PASS | 2500 | 0 | 0 |
| payment_orders.amount required | required | PASS | 2500 | 0 | 0 |
| payment_orders.currency required | required | PASS | 2500 | 0 | 0 |
| payment_orders.currency allowed values | enum | PASS | 2500 | 0 | 0 |
| payment_orders.created_at required | required | PASS | 2500 | 0 | 0 |
| payment_orders.status required | required | PASS | 2500 | 0 | 0 |
| payment_orders.status allowed values | enum | PASS | 2500 | 0 | 0 |
| payment_orders.captured_amount required | required | PASS | 2500 | 0 | 0 |
| payment_orders.refunded_amount required | required | PASS | 2500 | 0 | 0 |
| payment_orders.attempt_count required | required | PASS | 2500 | 0 | 0 |
| payment_attempts: primary key attempt_id unique | primary_key | PASS | 2750 | 0 | 0 |
| payment_attempts.attempt_id required | required | PASS | 2750 | 0 | 0 |
| payment_attempts.attempt_id ID format | id_format | PASS | 2750 | 0 | 0 |
| payment_attempts.payment_id required | required | PASS | 2750 | 0 | 0 |
| payment_attempts.payment_id -> payment_orders.payment_id | foreign_key | PASS | 2750 | 0 | 0 |
| payment_attempts.attempt_no required | required | PASS | 2750 | 0 | 0 |
| payment_attempts.attempted_at required | required | PASS | 2750 | 0 | 0 |
| payment_attempts.outcome required | required | PASS | 2750 | 0 | 0 |
| payment_attempts.outcome allowed values | enum | PASS | 2750 | 0 | 0 |
| payment_attempts.decline_code allowed values | enum | PASS | 2750 | 0 | 0 |
| payment_attempts.payment_method required | required | PASS | 2750 | 0 | 0 |
| payment_attempts.payment_method allowed values | enum | PASS | 2750 | 0 | 0 |
| processor_events: primary key ingest_id unique | primary_key | PASS | 5238 | 0 | 0 |
| processor_events.ingest_id required | required | PASS | 5238 | 0 | 0 |
| processor_events.ingest_id ID format | id_format | PASS | 5238 | 0 | 0 |
| processor_events.delivery_id required | required | PASS | 5238 | 0 | 0 |
| processor_events.delivery_id ID format | id_format | PASS | 5238 | 0 | 0 |
| processor_events.event_id required | required | PASS | 5238 | 0 | 0 |
| processor_events.event_id ID format | id_format | PASS | 5238 | 0 | 0 |
| processor_events.payment_id required | required | PASS | 5238 | 0 | 0 |
| processor_events.payment_id -> payment_orders.payment_id | foreign_key | PASS | 5238 | 0 | 0 |
| processor_events.attempt_id required | required | PASS | 5238 | 0 | 0 |
| processor_events.attempt_id -> payment_attempts.attempt_id | foreign_key | PASS | 5238 | 0 | 0 |
| processor_events.event_type required | required | PASS | 5238 | 0 | 0 |
| processor_events.event_type allowed values | enum | PASS | 5238 | 0 | 0 |
| processor_events.amount required | required | PASS | 5238 | 0 | 0 |
| processor_events.currency required | required | PASS | 5238 | 0 | 0 |
| processor_events.currency allowed values | enum | PASS | 5238 | 0 | 0 |
| processor_events.event_at required | required | PASS | 5238 | 0 | 0 |
| processor_events.received_at required | required | PASS | 5238 | 0 | 0 |
| settlement_batches: primary key batch_id unique | primary_key | PASS | 100 | 0 | 0 |
| settlement_batches.batch_id required | required | PASS | 100 | 0 | 0 |
| settlement_batches.batch_id ID format | id_format | PASS | 100 | 0 | 0 |
| settlement_batches.currency required | required | PASS | 100 | 0 | 0 |
| settlement_batches.currency allowed values | enum | PASS | 100 | 0 | 0 |
| settlement_batches.settlement_date required | required | PASS | 100 | 0 | 0 |
| settlement_batches.line_count required | required | PASS | 100 | 0 | 0 |
| settlement_batches.capture_count required | required | PASS | 100 | 0 | 0 |
| settlement_batches.refund_count required | required | PASS | 100 | 0 | 0 |
| settlement_batches.gross_captured required | required | PASS | 100 | 0 | 0 |
| settlement_batches.gross_refunded required | required | PASS | 100 | 0 | 0 |
| settlement_batches.fee_total required | required | PASS | 100 | 0 | 0 |
| settlement_batches.net_amount required | required | PASS | 100 | 0 | 0 |
| settlement_batches.status required | required | PASS | 100 | 0 | 0 |
| settlement_batches.status allowed values | enum | PASS | 100 | 0 | 0 |
| settlement_lines: primary key settlement_line_id unique | primary_key | PASS | 2415 | 0 | 0 |
| settlement_lines.settlement_line_id required | required | PASS | 2415 | 0 | 0 |
| settlement_lines.settlement_line_id ID format | id_format | PASS | 2415 | 0 | 0 |
| settlement_lines.batch_id required | required | PASS | 2415 | 0 | 0 |
| settlement_lines.batch_id -> settlement_batches.batch_id | foreign_key | PASS | 2415 | 0 | 0 |
| settlement_lines.event_id required | required | PASS | 2415 | 0 | 0 |
| settlement_lines.event_id -> processor_events.event_id | foreign_key | PASS | 2415 | 0 | 0 |
| settlement_lines.payment_id required | required | PASS | 2415 | 0 | 0 |
| settlement_lines.payment_id -> payment_orders.payment_id | foreign_key | PASS | 2415 | 0 | 0 |
| settlement_lines.line_type required | required | PASS | 2415 | 0 | 0 |
| settlement_lines.line_type allowed values | enum | PASS | 2415 | 0 | 0 |
| settlement_lines.gross_amount required | required | PASS | 2415 | 0 | 0 |
| settlement_lines.fee_amount required | required | PASS | 2415 | 0 | 0 |
| settlement_lines.net_amount required | required | PASS | 2415 | 0 | 0 |
| settlement_lines.currency required | required | PASS | 2415 | 0 | 0 |
| settlement_lines.currency allowed values | enum | PASS | 2415 | 0 | 0 |
| settlement_lines.event_date required | required | PASS | 2415 | 0 | 0 |
| bank_statement_lines: primary key bank_line_id unique | primary_key | PASS | 150 | 0 | 0 |
| bank_statement_lines.bank_line_id required | required | PASS | 150 | 0 | 0 |
| bank_statement_lines.bank_line_id ID format | id_format | PASS | 150 | 0 | 0 |
| bank_statement_lines.account_id required | required | PASS | 150 | 0 | 0 |
| bank_statement_lines.account_id allowed values | enum | PASS | 150 | 0 | 0 |
| bank_statement_lines.value_date required | required | PASS | 150 | 0 | 0 |
| bank_statement_lines.amount required | required | PASS | 150 | 0 | 0 |
| bank_statement_lines.currency required | required | PASS | 150 | 0 | 0 |
| bank_statement_lines.currency allowed values | enum | PASS | 150 | 0 | 0 |
| bank_statement_lines.direction required | required | PASS | 150 | 0 | 0 |
| bank_statement_lines.direction allowed values | enum | PASS | 150 | 0 | 0 |
| bank_statement_lines.counterparty required | required | PASS | 150 | 0 | 0 |
| bank_statement_lines.description required | required | PASS | 150 | 0 | 0 |
| event_dedup_log: primary key dedup_id unique | primary_key | PASS | 74 | 0 | 0 |
| event_dedup_log.dedup_id required | required | PASS | 74 | 0 | 0 |
| event_dedup_log.dedup_id ID format | id_format | PASS | 74 | 0 | 0 |
| event_dedup_log.ingest_id required | required | PASS | 74 | 0 | 0 |
| event_dedup_log.ingest_id -> processor_events.ingest_id | foreign_key | PASS | 74 | 0 | 0 |
| event_dedup_log.event_id required | required | PASS | 74 | 0 | 0 |
| event_dedup_log.duplicate_of_ingest_id required | required | PASS | 74 | 0 | 0 |
| event_dedup_log.duplicate_of_ingest_id -> processor_events.ingest_id | foreign_key | PASS | 74 | 0 | 0 |
| event_dedup_log.reason required | required | PASS | 74 | 0 | 0 |
| event_dedup_log.reason allowed values | enum | PASS | 74 | 0 | 0 |
| event_dedup_log.payload_identical required | required | PASS | 74 | 0 | 0 |
| event_dedup_log.payload_identical allowed values | enum | PASS | 74 | 0 | 0 |
| event_dedup_log.decision required | required | PASS | 74 | 0 | 0 |
| event_dedup_log.decision allowed values | enum | PASS | 74 | 0 | 0 |
| reconciliation_matches: primary key match_id unique | primary_key | PASS | 2568 | 0 | 0 |
| reconciliation_matches.match_id required | required | PASS | 2568 | 0 | 0 |
| reconciliation_matches.match_id ID format | id_format | PASS | 2568 | 0 | 0 |
| reconciliation_matches.match_level required | required | PASS | 2568 | 0 | 0 |
| reconciliation_matches.match_level allowed values | enum | PASS | 2568 | 0 | 0 |
| reconciliation_matches.settlement_line_id -> settlement_lines.settlement_line_id | foreign_key | PASS | 2568 | 0 | 0 |
| reconciliation_matches.batch_id -> settlement_batches.batch_id | foreign_key | PASS | 2568 | 0 | 0 |
| reconciliation_matches.bank_line_id -> bank_statement_lines.bank_line_id | foreign_key | PASS | 2568 | 0 | 0 |
| reconciliation_matches.match_status required | required | PASS | 2568 | 0 | 0 |
| reconciliation_matches.match_status allowed values | enum | PASS | 2568 | 0 | 0 |
| reconciliation_matches.match_method required | required | PASS | 2568 | 0 | 0 |
| reconciliation_matches.match_method allowed values | enum | PASS | 2568 | 0 | 0 |
| reconciliation_matches.currency allowed values | enum | PASS | 2568 | 0 | 0 |
| reconciliation_matches.matched_on required | required | PASS | 2568 | 0 | 0 |
| exceptions: primary key exception_id unique | primary_key | PASS | 14 | 0 | 0 |
| exceptions.exception_id required | required | PASS | 14 | 0 | 0 |
| exceptions.exception_id ID format | id_format | PASS | 14 | 0 | 0 |
| exceptions.exception_type required | required | PASS | 14 | 0 | 0 |
| exceptions.exception_type allowed values | enum | PASS | 14 | 0 | 0 |
| exceptions.severity required | required | PASS | 14 | 0 | 0 |
| exceptions.severity allowed values | enum | PASS | 14 | 0 | 0 |
| exceptions.entity_type required | required | PASS | 14 | 0 | 0 |
| exceptions.entity_type allowed values | enum | PASS | 14 | 0 | 0 |
| exceptions.entity_id required | required | PASS | 14 | 0 | 0 |
| exceptions.match_id -> reconciliation_matches.match_id | foreign_key | PASS | 14 | 0 | 0 |
| exceptions.currency allowed values | enum | PASS | 14 | 0 | 0 |
| exceptions.rule required | required | PASS | 14 | 0 | 0 |
| exceptions.status required | required | PASS | 14 | 0 | 0 |
| exceptions.status allowed values | enum | PASS | 14 | 0 | 0 |
| exceptions.created_at required | required | PASS | 14 | 0 | 0 |
| resolutions: primary key resolution_id unique | primary_key | PASS | 19 | 0 | 0 |
| resolutions.resolution_id required | required | PASS | 19 | 0 | 0 |
| resolutions.resolution_id ID format | id_format | PASS | 19 | 0 | 0 |
| resolutions.exception_id required | required | PASS | 19 | 0 | 0 |
| resolutions.exception_id -> exceptions.exception_id | foreign_key | PASS | 19 | 0 | 0 |
| resolutions.step_no required | required | PASS | 19 | 0 | 0 |
| resolutions.actor_role required | required | PASS | 19 | 0 | 0 |
| resolutions.actor_role allowed values | enum | PASS | 19 | 0 | 0 |
| resolutions.action required | required | PASS | 19 | 0 | 0 |
| resolutions.action allowed values | enum | PASS | 19 | 0 | 0 |
| resolutions.resulting_status required | required | PASS | 19 | 0 | 0 |
| resolutions.resulting_status allowed values | enum | PASS | 19 | 0 | 0 |
| resolutions.recorded_at required | required | PASS | 19 | 0 | 0 |
| resolutions.note required | required | PASS | 19 | 0 | 0 |
| merchants: row count = 100 | volume | PASS | 100 | 0 | 0 |
| payment_orders: row count = 2500 | volume | PASS | 2500 | 0 | 0 |
| payment_attempts: row count = 2750 | volume | PASS | 2750 | 0 | 0 |
| settlement_batches: row count = 100 | volume | PASS | 100 | 0 | 0 |
| bank_statement_lines: row count = 150 | volume | PASS | 150 | 0 | 0 |
| processor_events: one row per event_id | duplicates | PASS_WITH_LABELLED_ANOMALIES | 5238 | 74 | 74 |
| settlement_lines: one line per event_id | duplicates | PASS_WITH_LABELLED_ANOMALIES | 2415 | 3 | 3 |
| attempt time >= order created_at | date_order | PASS | 2750 | 0 | 0 |
| event time >= attempt time | date_order | PASS_WITH_LABELLED_ANOMALIES | 5164 | 3 | 3 |
| webhook received_at >= event_at | date_order | PASS | 5238 | 0 | 0 |
| refund after capture | date_order | PASS_WITH_LABELLED_ANOMALIES | 89 | 3 | 3 |
| settlement_date >= event_date | date_order | PASS | 2415 | 0 | 0 |
| fee_effective_from >= onboarded_date | date_order | PASS | 100 | 0 | 0 |
| batch totals = sum of lines; net = captured - refunded - fees | arithmetic | PASS | 100 | 0 | 0 |
| line net = gross - fee | arithmetic | PASS | 2415 | 0 | 0 |
| fee = round(gross x rate% + fixed) for captures, 0 for refunds | arithmetic | PASS | 2415 | 0 | 0 |
| amounts rounded to currency minor unit (JPY 0 dp) | arithmetic | PASS | 0 | 0 | 0 |
| order captured/refunded = sum of unique events; refund <= capture | arithmetic | PASS | 2500 | 0 | 0 |
| attempt sequence and event lifecycle per order | lifecycle | PASS | 2500 | 0 | 0 |
| order status derived from events | lifecycle | PASS | 2500 | 0 | 0 |
| event payment/currency consistent with attempt and order | lifecycle | PASS | 5164 | 0 | 0 |
| settlement line currency = batch currency | lifecycle | PASS | 2415 | 0 | 0 |
| every captured/refunded event appears in settlement | coverage | PASS_WITH_LABELLED_ANOMALIES | 2414 | 2 | 2 |
| ground truth not leaked into input/output columns | ground_truth | PASS | 11 | 0 | 0 |
| ground truth stored outside data folder | ground_truth | PASS | 1 | 0 | 0 |
