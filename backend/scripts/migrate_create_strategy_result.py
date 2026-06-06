"""
数据库迁移脚本：创建 strategy_result 表
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.utils.database import engine


def create_table():
    with engine.connect() as conn:
        # 检查表是否存在（SQLite 方式）
        result = conn.execute(text("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='strategy_result'
        """))
        exists = result.fetchone()
        
        if not exists:
            conn.execute(text("""
                CREATE TABLE strategy_result (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name VARCHAR(50) NOT NULL,
                    run_date DATE NOT NULL,
                    params JSON,
                    total_count INTEGER DEFAULT 0,
                    results JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX ix_strategy_result_strategy_name ON strategy_result (strategy_name)"))
            conn.execute(text("CREATE INDEX ix_strategy_result_run_date ON strategy_result (run_date)"))
            print("[OK] Created table: strategy_result")
        else:
            print("[SKIP] Table already exists: strategy_result")
        
        conn.commit()
        print("[DONE] Migration completed!")


if __name__ == '__main__':
    create_table()
