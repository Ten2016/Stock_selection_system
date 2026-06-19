from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings
from app.utils.startup_checks import (
    ensure_sqlite_database_path,
    repair_stock_kline_schema,
    collect_table_status,
)
from app.utils.data_migrations import repair_json_columns


SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    ensure_sqlite_database_path(SQLALCHEMY_DATABASE_URL)
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        duplicate_rows = repair_stock_kline_schema(conn)
        repaired_json = repair_json_columns(conn)
        table_report = collect_table_status(conn)

    print("=" * 80)
    print("[STARTUP CHECK] Database and schema self-check")
    print(f"[STARTUP CHECK] Database URL: {settings.DATABASE_URL}")
    for table, info in table_report.items():
        status = "OK" if info["exists"] else "MISSING"
        rows = info["rows"] if info["rows"] is not None else "N/A"
        print(f"[STARTUP CHECK] {table}: {status}, rows={rows}")
    print(f"[STARTUP CHECK] stock_kline duplicate rows removed: {duplicate_rows}")
    print(f"[STARTUP CHECK] JSON-like columns repaired: {repaired_json}")
    print("[STARTUP CHECK] stock_kline indexes: uq_stock_kline_code_date ensured")
    print("[STARTUP CHECK] schema repair completed")
    print("=" * 80)

