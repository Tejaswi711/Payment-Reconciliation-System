import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
 
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
 
 
BASE_DIR = Path(__file__).resolve().parent.parent
 
DB_PATH = BASE_DIR / "output" / "starter" / "sql" / "payments.db"
PIPELINE_PATH = BASE_DIR / "backend" / "run_all.py"
BACKEND_DIR = BASE_DIR / "backend"
REPORT_PATH = BASE_DIR / "output" / "starter" / "report.html"
 
st.set_page_config(
    page_title="Payment Reconciliation System",
    layout="wide",
)
 
 
st.markdown(
    """
<style>
    .stApp {
        background-color: #f5f7fb;
    }
 
    .main-title {
        font-size: 34px;
        font-weight: 700;
        color: #172554;
    }
 
    .subtitle {
        color: #64748b;
        font-size: 15px;
    }
 
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 18px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }
 
    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] label p,
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] p {
        color: #475569 !important;
        font-weight: 600;
    }
 
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] div {
        color: #172554 !important;
        font-weight: 700;
    }
 
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""",
    unsafe_allow_html=True,
)
 
 
def get_connection():
    return sqlite3.connect(DB_PATH)
 
 
def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'
 
 
def get_tables():
    if not DB_PATH.exists():
        return []
 
    query = """
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    AND name NOT LIKE 'sqlite_%'
    ORDER BY name
    """
 
    with closing(get_connection()) as conn:
        return pd.read_sql_query(query, conn)["name"].tolist()
 
 
def get_table_data(table_name):
    with closing(get_connection()) as conn:
        return pd.read_sql_query(
            f"SELECT * FROM {quote_identifier(table_name)} LIMIT 1000",
            conn,
        )
 
 
def get_table_count(table_name):
    with closing(get_connection()) as conn:
        result = conn.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table_name)}"
        ).fetchone()
        return result[0]
 
 
def show_dataframe(data):
    # Works on both older and newer Streamlit versions
    try:
        st.dataframe(data, width="stretch", hide_index=True)
    except TypeError:
        st.dataframe(data, use_container_width=True, hide_index=True)
 
 
st.markdown(
    '<div class="main-title">Payment Reconciliation System</div>',
    unsafe_allow_html=True,
)
 
st.markdown(
    '<div class="subtitle">'
    "Smart payment monitoring, matching and exception management"
    "</div>",
    unsafe_allow_html=True,
)
 
st.divider()
 
 
st.sidebar.title("Payment Recon")
 
page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Transaction Data",
        "Database Explorer",
        "Reconciliation Report",
    ],
)
 
st.sidebar.divider()
 
st.sidebar.info(
    "Payment Reconciliation System\n\n"
    "Frontend: Streamlit\n\n"
    "Backend: Python\n\n"
    "Database: SQLite"
)
 
 
if page == "Dashboard":
 
    st.subheader("Dashboard Overview")
 
    st.write("Monitor payment transactions and reconciliation performance.")
 
    if st.button("Run Reconciliation", type="primary"):
 
        if not PIPELINE_PATH.exists():
            st.error("run_all.py not found.")
 
        else:
            env = os.environ.copy()
            extra_paths = [str(BASE_DIR), str(BACKEND_DIR)]
            if env.get("PYTHONPATH"):
                extra_paths.append(env["PYTHONPATH"])
            env["PYTHONPATH"] = os.pathsep.join(extra_paths)
 
            with st.spinner("Running reconciliation pipeline..."):
                result = subprocess.run(
                    [sys.executable, str(PIPELINE_PATH)],
                    cwd=BASE_DIR,
                    capture_output=True,
                    text=True,
                    env=env,
                )
 
            if result.returncode == 0:
                st.success("Pipeline completed successfully.")
                st.cache_data.clear()
            else:
                st.error("Pipeline execution failed.")
 
            with st.expander("Execution Logs", expanded=result.returncode != 0):
                st.text("OUTPUT:")
                st.code(result.stdout or "No output")
 
                if result.stderr:
                    st.text("ERRORS:")
                    st.code(result.stderr)
 
    st.divider()
 
    tables = get_tables()
 
    if not tables:
        st.warning("Database not found. Run your backend pipeline first.")
 
    else:
        counts = {table: get_table_count(table) for table in tables}
 
        st.subheader("Database Statistics")
 
        preferred_tables = [
            "merchants",
            "payment_orders",
            "payment_attempts",
            "processor_events",
        ]
 
        available = [t for t in preferred_tables if t in counts]
 
        if available:
            columns = st.columns(len(available))
 
            for column, table in zip(columns, available):
                with column:
                    st.metric(
                        table.replace("_", " ").title(),
                        f"{counts[table]:,}",
                    )
 
        st.divider()
 
        st.subheader("Database Summary")
 
        summary = pd.DataFrame(
            [
                {"Table Name": table, "Total Records": count}
                for table, count in counts.items()
            ]
        )
 
        show_dataframe(summary)
 
 
elif page == "Transaction Data":
 
    st.subheader("Transaction Data")
 
    tables = get_tables()
 
    if not tables:
        st.warning("Database not found.")
 
    else:
        preferred_tables = [
            "payment_orders",
            "payment_attempts",
            "processor_events",
            "settlement_batches",
            "settlement_lines",
            "bank_statement_lines",
            "reconciliation_matches",
            "exceptions",
            "resolutions",
        ]
 
        available = [t for t in preferred_tables if t in tables]
 
        if not available:
            available = tables
 
        selected_table = st.selectbox("Select Transaction Category", available)
 
        data = get_table_data(selected_table)
 
        st.metric("Total Records", f"{get_table_count(selected_table):,}")
 
        show_dataframe(data)
 
        st.download_button(
            "Download CSV",
            data=data.to_csv(index=False).encode("utf-8"),
            file_name=f"{selected_table}.csv",
            mime="text/csv",
        )
 
 
elif page == "Database Explorer":
 
    st.subheader("Database Explorer")
 
    tables = get_tables()
 
    if not tables:
        st.warning("SQLite database not found.")
 
    else:
        selected_table = st.selectbox("Choose Database Table", tables)
 
        data = get_table_data(selected_table)
 
        col1, col2 = st.columns(2)
 
        with col1:
            st.metric("Total Records", f"{get_table_count(selected_table):,}")
 
        with col2:
            st.metric("Total Columns", len(data.columns))
 
        st.subheader("Table Records")
 
        show_dataframe(data)
 
 
elif page == "Reconciliation Report":
 
    st.subheader("Reconciliation Report")
 
    if REPORT_PATH.exists():
 
        st.success("Reconciliation report is available.")
 
        with open(REPORT_PATH, "r", encoding="utf-8") as file:
            report_html = file.read()
 
        st.download_button(
            "Download HTML Report",
            data=report_html,
            file_name="reconciliation_report.html",
            mime="text/html",
        )
 
        components.html(report_html, height=800, scrolling=True)
 
    else:
        st.warning("Report not found. Run the backend pipeline first.")
 
 
st.divider()
 
st.caption(
    "Payment Reconciliation System | "
    "Streamlit Frontend | Python Backend | SQLite Database"
)