from collections import OrderedDict
from pathlib import Path
from sqlalchemy import inspect, text

CHECK_TABLES = ["stock_basic", "stock_kline", "strategy", "strategy_result", "sync_record", "selection_result"]


def ensure_sqlite_database_path(database_url: str):
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.replace("sqlite:///", ""))
        if db_path.parent:
            db_path.parent.mkdir(parents=True, exist_ok=True)


def repair_stock_kline_schema(conn):
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(stock_kline)")).fetchall()}
    if "dividend_info" not in columns:
        conn.execute(text("ALTER TABLE stock_kline ADD COLUMN dividend_info JSON"))

    indexes = {row[1] for row in conn.execute(text("PRAGMA index_list(stock_kline)")).fetchall()}
    if "uq_stock_kline_code_date" not in indexes:
        conn.execute(text("CREATE UNIQUE INDEX uq_stock_kline_code_date ON stock_kline(stock_code, trade_date)"))

    dup_count = conn.execute(text(
        "SELECT COUNT(*) - COUNT(DISTINCT stock_code || '|' || trade_date) FROM stock_kline"
    )).scalar() or 0
    if dup_count > 0:
        conn.execute(text("""
            DELETE FROM stock_kline
            WHERE id NOT IN (
                SELECT MAX(id) FROM stock_kline GROUP BY stock_code, trade_date
            )
        """))
        conn.execute(text("DROP INDEX IF EXISTS uq_stock_kline_code_date"))
        conn.execute(text("CREATE UNIQUE INDEX uq_stock_kline_code_date ON stock_kline(stock_code, trade_date)"))
    return int(dup_count)


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
