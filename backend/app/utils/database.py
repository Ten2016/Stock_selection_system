from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings
import os


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


def _migrate_stock_kline_unique(conn):
    dup_count = conn.execute(text(
        "SELECT COUNT(*) - COUNT(DISTINCT stock_code || '|' || trade_date) FROM stock_kline"
    )).scalar()
    if dup_count and dup_count > 0:
        conn.execute(text("""
            DELETE FROM stock_kline
            WHERE id NOT IN (
                SELECT MAX(id) FROM stock_kline GROUP BY stock_code, trade_date
            )
        """))
        conn.commit()
        print(f"Removed {dup_count} duplicate stock_kline rows.")

    existing = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='uq_stock_kline_code_date'"
    )).fetchone()
    if not existing:
        conn.execute(text(
            "CREATE UNIQUE INDEX uq_stock_kline_code_date "
            "ON stock_kline(stock_code, trade_date)"
        ))
        conn.commit()
        print("Created unique index uq_stock_kline_code_date on stock_kline.")


def init_db():
    os.makedirs(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE stock_kline ADD COLUMN dividend_info JSON"))
            conn.commit()
            print("Added dividend_info column to stock_kline table.")
        except Exception:
            pass

        _migrate_stock_kline_unique(conn)

    print("Database initialized successfully.")
