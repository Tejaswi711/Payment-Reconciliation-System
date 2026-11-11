from datetime import date

GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = 20261022          
ID_YEAR = 2026                  
CALENDAR_START = date(2026, 1, 1)
AS_OF_TIMESTAMP = "2026-12-31T23:59:59"   

PROCESSOR_NAME = "NOVAPAY PROCESSING LTD"
PLATFORM_NAME = "DEMO PAYMENTS PLATFORM"


SCALES = {
    "starter": {"merchants": 100, "orders": 2500, "extra_attempts": 250,
                "settlement_days": 25, "bank_lines": 150},
    "full": {"merchants": 2000, "orders": 50000, "extra_attempts": 5000,
             "settlement_days": 250, "bank_lines": 5000},
}


EDGE_CASES = {
    "starter": {"duplicate_settlement_line": 3, "bank_fee_difference": 2,
                "refund_before_capture": 3, "missing_from_settlement": 2,
                "missing_payout": 1, "unmatched_bank_line": 1,
                "currency_mismatch": 2, "duplicate_ingestion": 4},
    "full": {"duplicate_settlement_line": 20, "bank_fee_difference": 10,
             "refund_before_capture": 15, "missing_from_settlement": 10,
             "missing_payout": 5, "unmatched_bank_line": 5,
             "currency_mismatch": 8, "duplicate_ingestion": 25},
}


RATES = {
    "single_attempt_success": 0.95,  
    "retry_success": 0.80,           
    "full_refund": 0.02,
    "partial_refund": 0.04,
    "delayed_settlement": 0.03,      
    "duplicate_webhook": 0.015,      
    "rounding_difference": 0.03,     
    "delayed_payout": 0.05,          
}
MAX_EXTRA_SETTLEMENT_DELAY = 5
MAX_REFUND_AFTER_DAYS = 15

CURRENCIES = {
    "USD": {"decimals": 2, "weight": 50, "amount_scale": 1.0, "fixed_fee": "0.30",
            "countries": ["US"], "tolerance": "0.05", "account_id": "ACC-USD-001"},
    "EUR": {"decimals": 2, "weight": 25, "amount_scale": 0.92, "fixed_fee": "0.25",
            "countries": ["DE", "FR", "NL", "ES", "IE"], "tolerance": "0.05",
            "account_id": "ACC-EUR-001"},
    "GBP": {"decimals": 2, "weight": 15, "amount_scale": 0.79, "fixed_fee": "0.20",
            "countries": ["GB"], "tolerance": "0.05", "account_id": "ACC-GBP-001"},
    "JPY": {"decimals": 0, "weight": 10, "amount_scale": 150.0, "fixed_fee": "40",
            "countries": ["JP"], "tolerance": "5", "account_id": "ACC-JPY-001"},
}

SETTLEMENT_WINDOW_DAYS = 14  
BANK_DATE_WINDOW_DAYS = 5     
