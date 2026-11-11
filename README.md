# Payment Reconciliation System

## Project Overview

The **Payment Reconciliation System** is designed to reconcile payment instructions, payment processor events, settlement records, and bank statement entries.

It identifies matching transactions, detects discrepancies, records exceptions, and tracks their resolution history.

The project uses synthetic payment data to simulate real-world payment reconciliation scenarios.

## Key Features

- Synthetic payment data generation.
- Payment instruction and processor event reconciliation.
- Settlement and bank statement matching.
- Duplicate event detection and deduplication.
- Exception identification and tracking.
- Resolution history management.
- Data validation and evaluation.
- Reproducibility checks.
- SQLite database integration.
- Interactive Streamlit dashboard.
- HTML reconciliation report generation.
- CSV, JSON, and SQL outputs.

## Technology Stack

| Category | Technologies |
|---|---|
| Programming Language | Python |
| Database | SQLite |
| Frontend | Streamlit |
| Data Processing | Pandas, NumPy |
| Testing | Pytest |
| Data Storage | CSV, JSON, SQL |
| Reporting | HTML |

## Project Structure

```text
payment-recon/
│
├── backend/
│   ├── common.py
│   ├── config.py
│   ├── generate_data.py
│   ├── reconcile.py
│   ├── validate.py
│   ├── evaluate.py
│   ├── export_sql.py
│   ├── schema.py
│   ├── report.py
│   ├── reproduce.py
│   └── run_all.py
│
├── frontend/
│   └── app.py
│
├── tests/
│   └── test_pipeline.py
│
├── docs/
│   └── data_dictionary.md
│
├── output/
│   └── starter/
│       ├── sql/
│       │   ├── schema.sql
│       │   ├── seed.sql
│       │   └── payments.db
│       │
│       ├── report.html
│       ├── validation_summary.json
│       ├── evaluation.json
│       ├── reproducibility_report.json
│       └── manifest.json
│
├── README.md
└── requirements.txt
```

## Database Design

The SQLite database contains 11 tables and 2 views.

### Main Tables

1. `merchants`
2. `payment_orders`
3. `payment_attempts`
4. `processor_events`
5. `settlement_batches`
6. `settlement_lines`
7. `bank_statement_lines`
8. `event_dedup_log`
9. `reconciliation_matches`
10. `exceptions`
11. `resolutions`

### Database Views

- `exception_current_status` – Displays the current status of exceptions based on resolution history.
- `processor_events_unique` – Provides unique processor events while excluding duplicate ingestions.

### SQL Files

All database files are located in `output/starter/sql/`:

- `schema.sql` – Table definitions, constraints, and views.
- `seed.sql` – SQL seed data.
- `payments.db` – SQLite database.

## Installation and Setup

### 1. Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd payment-recon
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Project

### 1. Run the Complete Pipeline

From the project root directory:

```bash
python backend/run_all.py
```

This runs the data generation, reconciliation, validation, evaluation, database export, reporting, and reproducibility workflow.

### 2. Launch the Streamlit Dashboard

```bash
streamlit run frontend/app.py
```

The dashboard provides access to transaction data, database tables, reconciliation reports, and pipeline execution.

### 3. Run Tests

```bash
python -m pytest tests/ -v
```

## Validation Results

The completed pipeline produced the following results:

| Validation Metric | Result |
|---|---:|
| Total validation checks | 192 |
| PASS | 187 |
| PASS_WITH_LABELLED_ANOMALIES | 5 |
| Foreign key violations | 0 |
| Reproducibility check | Passed |

The five anomaly-related validation categories are explicitly labeled and retained for evaluation rather than silently discarded.

## Evaluation Highlights

- Event match rate: 99.92%
- Settlement batch auto-match rate: 95%
- Anomaly recall: 100%
- Exception precision: 100%
- Duplicate processor event ingestions ignored: 74

## Generated Outputs

The pipeline generates:

| File | Purpose |
|---|---|
| `payments.db` | SQLite database |
| `schema.sql` | Database schema |
| `seed.sql` | SQL seed data |
| `report.html` | Reconciliation report |
| `validation_summary.json` | Validation results |
| `evaluation.json` | Evaluation metrics |
| `reproducibility_report.json` | Reproducibility results |
| `manifest.json` | Generated data and run metadata |
| `data_dictionary.md` | Database documentation |

## Testing

The project includes automated tests in `tests/test_pipeline.py`.

Run the tests using:

```bash
python -m pytest tests/ -v
```

## Project Objective

The objective is to build a reliable and reproducible payment reconciliation solution that can identify transaction mismatches, detect anomalies, manage exceptions, and maintain a traceable resolution history.

The system is designed to make payment reconciliation more transparent, accurate, and easier to monitor.
