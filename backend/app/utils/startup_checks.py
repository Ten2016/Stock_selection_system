from collections import OrderedDict
from pathlib import Path
from sqlalchemy import inspect, text

CHECK_TABLES = ["stock_basic", "stock_kline", "strategy", "strategy_result", "sync_record", "selection_result"]


def ensure_sqlite_database_path(database_url: str):
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.replace("sqlite:///", ""))
        if db_path.parent:
            db_path.parent.mkdir(parents=True, exist_ok=True)


def collect_table_status(conn):
    inspector = inspect(conn)
    report = OrderedDict()
    for table in CHECK_TABLES:
        exists = inspector.has_table(table)
        row_count = None
        if exists:
            try:
                row_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0
            except Exception:
                row_count = None
        report[table] = {"exists": exists, "rows": row_count}
    return report
