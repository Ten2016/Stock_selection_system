"""
数据库迁移脚本：添加新字段到 stock_basic 表
- pe_ratio: 动态市盈率（TTM）
- pe_ratio_static: 静态市盈率
- pb_ratio: 市净率
- ytd_change_pct: 今年涨跌幅
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.utils.database import engine


def add_columns():
    with engine.connect() as conn:
        # 获取 stock_basic 表的现有列
        result = conn.execute(text("PRAGMA table_info(stock_basic)"))
        existing_columns = [row[1] for row in result.fetchall()]
        
        columns_to_add = [
            ('pe_ratio', 'DECIMAL(10, 2)'),
            ('pe_ratio_static', 'DECIMAL(10, 2)'),
            ('pb_ratio', 'DECIMAL(10, 2)'),
            ('ytd_change_pct', 'DECIMAL(10, 2)'),
        ]
        
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                conn.execute(text(f"ALTER TABLE stock_basic ADD COLUMN {col_name} {col_type}"))
                print(f"[OK] Added column: {col_name}")
            else:
                print(f"[SKIP] Column already exists: {col_name}")
        
        conn.commit()
        print("[DONE] Migration completed!")


if __name__ == '__main__':
    add_columns()
