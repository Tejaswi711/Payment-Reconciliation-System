# Payment Reconciliation System — Data Dictionary

## 1. Overview

This data dictionary describes the database structure of the Payment Reconciliation System.

The database uses SQLite and contains 11 tables and 2 views.

The database stores information about merchants, payment orders, payment attempts, processor events, settlement batches, settlement lines, bank statement lines, duplicate event records, reconciliation matches, exceptions, and resolutions.

## 2. Database Tables

### 2.1 merchants

Stores merchant information and settlement configuration.

| Column | Data Type | Description |
|---|---|---|
| merchant_id | TEXT | Unique merchant identifier (Primary Key) |
| merchant_name | TEXT | Merchant name |
| country | TEXT | Merchant country |
| settlement_currency | TEXT | Settlement currency |
| category | TEXT | Merchant business category |
| fee_rate_pct | NUMERIC(18,2) | Percentage-based transaction fee |
| fixed_fee | NUMERIC(18,2) | Fixed transaction fee |
| settlement_delay_days | INTEGER | Settlement delay in days |
| status | TEXT | Merchant status |
| onboarded_date | TEXT | Merchant onboarding date |
| fee_effective_from | TEXT | Date from which the fee applies |

### 2.2 payment_orders

Stores customer payment orders.

| Column | Data Type | Description |
|---|---|---|
| payment_id | TEXT | Unique payment identifier (Primary Key) |
| merchant_id | TEXT | Associated merchant (Foreign Key) |
| customer_ref | TEXT | Customer reference |
| amount | NUMERIC(18,2) | Payment amount |
| currency | TEXT | Payment currency |
| created_at | TEXT | Payment creation timestamp |
| status | TEXT | Payment status |
| captured_amount | NUMERIC(18,2) | Captured payment amount |
| refunded_amount | NUMERIC(18,2) | Refunded payment amount |
| attempt_count | INTEGER | Number of payment attempts |

### 2.3 payment_attempts

Stores individual attempts made to process payments.

| Column | Data Type | Description |
|---|---|---|
| attempt_id | TEXT | Unique attempt identifier (Primary Key) |
| payment_id | TEXT | Associated payment (Foreign Key) |
| attempt_no | INTEGER | Attempt sequence number |
| attempted_at | TEXT | Attempt timestamp |
| outcome | TEXT | Attempt result |
| decline_code | TEXT | Decline reason, if applicable |
| payment_method | TEXT | Payment method used |

### 2.4 processor_events

Stores payment processor event records.

| Column | Data Type | Description |
|---|---|---|
| ingest_id | TEXT | Unique ingestion identifier (Primary Key) |
| delivery_id | TEXT | Processor delivery identifier |
| event_id | TEXT | Processor event identifier |
| payment_id | TEXT | Associated payment (Foreign Key) |
| attempt_id | TEXT | Associated payment attempt (Foreign Key) |
| event_type | TEXT | Type of processor event |
| amount | NUMERIC(18,2) | Event amount |
| currency | TEXT | Event currency |
| event_at | TEXT | Time the event occurred |
| received_at | TEXT | Time the event was received |

### 2.5 settlement_batches

Stores settlement batch information.

| Column | Data Type | Description |
|---|---|---|
| batch_id | TEXT | Unique settlement batch identifier (Primary Key) |
| currency | TEXT | Settlement currency |
| settlement_date | TEXT | Settlement date |
| line_count | INTEGER | Total settlement lines |
| capture_count | INTEGER | Number of capture transactions |
| refund_count | INTEGER | Number of refund transactions |
| gross_captured | NUMERIC(18,2) | Total captured amount |
| gross_refunded | NUMERIC(18,2) | Total refunded amount |
| fee_total | NUMERIC(18,2) | Total settlement fees |
| net_amount | NUMERIC(18,2) | Net settlement amount |
| status | TEXT | Settlement batch status |

### 2.6 settlement_lines

Stores individual transaction lines within settlement batches.

| Column | Data Type | Description |
|---|---|---|
| settlement_line_id | TEXT | Unique settlement line identifier (Primary Key) |
| batch_id | TEXT | Associated settlement batch (Foreign Key) |
| event_id | TEXT | Related processor event identifier |
| payment_id | TEXT | Associated payment (Foreign Key) |
| line_type | TEXT | Capture or refund |
| gross_amount | NUMERIC(18,2) | Gross transaction amount |
| fee_amount | NUMERIC(18,2) | Fee charged |
| net_amount | NUMERIC(18,2) | Net transaction amount |
| currency | TEXT | Transaction currency |
| event_date | TEXT | Event date |

### 2.7 bank_statement_lines

Stores transaction entries from bank statements.

| Column | Data Type | Description |
|---|---|---|
| bank_line_id | TEXT | Unique bank statement line identifier (Primary Key) |
| account_id | TEXT | Bank account identifier |
| value_date | TEXT | Bank transaction value date |
| amount | NUMERIC(18,2) | Bank transaction amount |
| currency | TEXT | Transaction currency |
| direction | TEXT | Credit or debit |
| counterparty | TEXT | Transaction counterparty |
| reference | TEXT | Bank transaction reference |
| description | TEXT | Bank transaction description |

### 2.8 event_dedup_log

Stores duplicate processor event ingestion records and deduplication decisions.

| Column | Data Type | Description |
|---|---|---|
| dedup_id | TEXT | Unique deduplication record identifier (Primary Key) |
| ingest_id | TEXT | Duplicate ingestion record (Foreign Key) |
| event_id | TEXT | Processor event identifier |
| duplicate_of_ingest_id | TEXT | Original ingestion identifier (Foreign Key) |
| reason | TEXT | Reason for deduplication |
| payload_identical | TEXT | Indicates whether payloads are identical |
| decision | TEXT | Deduplication decision |

### 2.9 reconciliation_matches

Stores reconciliation matching results between processor events, settlement records, batches, and bank statement lines.

| Column | Data Type | Description |
|---|---|---|
| match_id | TEXT | Unique reconciliation match identifier (Primary Key) |
| match_level | TEXT | Reconciliation matching level |
| event_id | TEXT | Processor event identifier |
| settlement_line_id | TEXT | Settlement line reference (Foreign Key) |
| batch_id | TEXT | Settlement batch reference (Foreign Key) |
| bank_line_id | TEXT | Bank statement line reference (Foreign Key) |
| match_status | TEXT | Matching result |
| match_method | TEXT | Method used for matching |
| expected_amount | NUMERIC(18,2) | Expected transaction amount |
| actual_amount | NUMERIC(18,2) | Actual transaction amount |
| difference | NUMERIC(18,2) | Difference between amounts |
| currency | TEXT | Transaction currency |
| tolerance | NUMERIC(18,2) | Allowed matching tolerance |
| matched_on | TEXT | Matching timestamp |

### 2.10 exceptions

Stores reconciliation discrepancies and exception records.

| Column | Data Type | Description |
|---|---|---|
| exception_id | TEXT | Unique exception identifier (Primary Key) |
| exception_type | TEXT | Type of reconciliation exception |
| severity | TEXT | Exception severity |
| entity_type | TEXT | Type of related entity |
| entity_id | TEXT | Related entity identifier |
| related_ids | TEXT | Related record identifiers |
| match_id | TEXT | Related reconciliation match (Foreign Key) |
| amount_difference | NUMERIC(18,2) | Amount discrepancy |
| currency | TEXT | Transaction currency |
| rule | TEXT | Rule that triggered the exception |
| status | TEXT | Exception status |
| created_at | TEXT | Exception creation timestamp |

### 2.11 resolutions

Stores resolution actions and the history of exception handling.

| Column | Data Type | Description |
|---|---|---|
| resolution_id | TEXT | Unique resolution identifier (Primary Key) |
| exception_id | TEXT | Associated exception (Foreign Key) |
| step_no | INTEGER | Resolution sequence number |
| actor_role | TEXT | Role of the person or system performing the action |
| action | TEXT | Resolution action performed |
| resulting_status | TEXT | Resulting exception status |
| recorded_at | TEXT | Resolution timestamp |
| note | TEXT | Resolution details |

## 3. Database Views

### 3.1 exception_current_status

Provides the current status of each exception based on its latest resolution step.

Selected columns:

- exception_id
- exception_type
- severity
- entity_type
- entity_id
- current_status
- last_actor

The view uses the latest `step_no` from the resolutions table. Resolution history is preserved rather than overwritten.

### 3.2 processor_events_unique

Provides processor event records after idempotent deduplication.

It excludes ingestion records whose `ingest_id` appears in the `event_dedup_log` table.

## 4. Primary Key Relationships

Each table has a primary key that uniquely identifies its records.

| Parent Table | Child Table | Relationship |
|---|---|---|
| merchants | payment_orders | merchant_id |
| payment_orders | payment_attempts | payment_id |
| payment_orders | processor_events | payment_id |
| payment_attempts | processor_events | attempt_id |
| settlement_batches | settlement_lines | batch_id |
| payment_orders | settlement_lines | payment_id |
| processor_events | event_dedup_log | ingest_id |
| processor_events | event_dedup_log | duplicate_of_ingest_id |
| settlement_lines | reconciliation_matches | settlement_line_id |
| settlement_batches | reconciliation_matches | batch_id |
| bank_statement_lines | reconciliation_matches | bank_line_id |
| reconciliation_matches | exceptions | match_id |
| exceptions | resolutions | exception_id |

## 5. Data Constraints

The database uses the following constraints:

- PRIMARY KEY constraints for unique record identification.
- FOREIGN KEY constraints for relationships between tables.
- NOT NULL constraints for mandatory fields.
- CHECK constraints to restrict values to supported currencies, statuses, categories, event types, and actions.

## 6. Supported Currencies

- USD
- EUR
- GBP
- JPY

## 7. Reconciliation Status Values

**Match statuses:**
- MATCHED
- MATCHED_WITH_TOLERANCE
- PARTIAL
- UNMATCHED
- DUPLICATE
- OUT_OF_SCOPE

**Exception severity:**
- LOW
- MEDIUM
- HIGH

**Resolution statuses:**
- RESOLVED
- PENDING_PROCESSOR
- IN_REVIEW
- ESCALATED
- UNDER_COMPLIANCE_REVIEW

## 8. Database Technology

- Database Engine: SQLite
- Schema Definition: SQL
- Database File: `payments.db`
- Schema Source: `schema.py`
- Schema Export: `schema.sql`

---

**Document:** Payment Reconciliation System Data Dictionary

**Purpose:** Database documentation and reference for the project.
