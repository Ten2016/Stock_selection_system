import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.database import engine
from sqlalchemy import text

def migrate():
    print("Running database migration for sync_record table...")
    
    with engine.connect() as conn:
        migrations = [
            ("Add success_count column", "ALTER TABLE sync_record ADD COLUMN success_count INTEGER DEFAULT 0"),
            ("Add skipped_count column", "ALTER TABLE sync_record ADD COLUMN skipped_count INTEGER DEFAULT 0"),
            ("Add failed_count column", "ALTER TABLE sync_record ADD COLUMN failed_count INTEGER DEFAULT 0"),
            ("Add no_data_count column", "ALTER TABLE sync_record ADD COLUMN no_data_count INTEGER DEFAULT 0"),
            ("Add failed_stocks column", "ALTER TABLE sync_record ADD COLUMN failed_stocks TEXT"),
            ("Add no_data_stocks column", "ALTER TABLE sync_record ADD COLUMN no_data_stocks TEXT"),
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
