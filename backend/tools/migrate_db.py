import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.database import engine
from sqlalchemy import text

def migrate():
    print("Running database migration...")
    
    with engine.connect() as conn:
        migrations = [
            ("Add ma30 column", "ALTER TABLE stock_kline ADD COLUMN ma30 DECIMAL(10, 2)"),
            ("Add ma120 column", "ALTER TABLE stock_kline ADD COLUMN ma120 DECIMAL(10, 2)"),
            ("Add composite index", "CREATE INDEX IF NOT EXISTS idx_stock_code_trade_date ON stock_kline(stock_code, trade_date)"),
        ]
        
        for desc, sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"SUCCESS: {desc}")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                    print(f"INFO: {desc} - already exists")
                else:
                    print(f"ERROR: {desc} - {e}")
                    raise
    
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
