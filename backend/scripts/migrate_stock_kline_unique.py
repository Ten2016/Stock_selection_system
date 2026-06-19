"""为 stock_kline 去重并添加 (stock_code, trade_date) 唯一约束。"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.utils.database import engine


def migrate():
    with engine.connect() as conn:
        dup_count = conn.execute(text(
            "SELECT COUNT(*) - COUNT(DISTINCT stock_code || '|' || trade_date) FROM stock_kline"
        )).scalar()
        if dup_count and dup_count > 0:
            print(f"[INFO] Removing {dup_count} duplicate kline rows...")
            conn.execute(text("""
                DELETE FROM stock_kline
                WHERE id NOT IN (
                    SELECT MAX(id) FROM stock_kline GROUP BY stock_code, trade_date
                )
            """))
            conn.commit()
            print("[OK] Duplicates removed.")

        existing = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='uq_stock_kline_code_date'"
        )).fetchone()
        if not existing:
            print("[INFO] Creating unique index uq_stock_kline_code_date...")
            conn.execute(text(
                "CREATE UNIQUE INDEX uq_stock_kline_code_date "
                "ON stock_kline(stock_code, trade_date)"
            ))
            conn.commit()
            print("[OK] Unique index created.")
        else:
            print("[OK] Unique index already exists.")


if __name__ == "__main__":
    migrate()
