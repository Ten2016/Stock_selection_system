"""
独立 MACD 指标补算脚本
用法：cd backend && python scripts/repair_macd.py
功能：
  1. 自动检查 stock_kline 表是否有 dif/dea/macd 字段，没有则新增
  2. 遍历所有股票，重新计算 MACD 指标并写回数据库
  3. 只更新 MACD 相关字段，不触碰其他指标
"""
import os
import sys
import time
import sqlite3
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "stock.db"


def calculate_macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_hist = 2 * (dif - dea)
    return dif, dea, macd_hist


def ensure_columns_exist(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(stock_kline)")
    columns = {row[1] for row in cursor.fetchall()}
    
    new_columns = []
    if 'dif' not in columns:
        new_columns.append('dif DECIMAL(10,4)')
    if 'dea' not in columns:
        new_columns.append('dea DECIMAL(10,4)')
    if 'macd' not in columns:
        new_columns.append('macd DECIMAL(10,4)')
    
    if new_columns:
        for col in new_columns:
            print(f"  新增字段: {col}")
            cursor.execute(f"ALTER TABLE stock_kline ADD COLUMN {col}")
        conn.commit()
        print("  字段新增完成")
    else:
        print("  dif/dea/macd 字段已存在，跳过")


def get_all_stock_codes(conn: sqlite3.Connection) -> list:
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT stock_code FROM stock_kline ORDER BY stock_code")
    return [row[0] for row in cursor.fetchall()]


def repair_stock_macd(conn: sqlite3.Connection, stock_code: str) -> int:
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT trade_date, close FROM stock_kline WHERE stock_code = ? ORDER BY trade_date ASC",
        (stock_code,)
    )
    rows = cursor.fetchall()
    
    if not rows:
        return 0
    
    trade_dates = [row[0] for row in rows]
    closes = pd.Series([row[1] for row in rows], dtype=float)
    
    dif, dea, macd_hist = calculate_macd(closes)
    
    update_data = []
    for i in range(len(trade_dates)):
        d = dif.iloc[i]
        e = dea.iloc[i]
        m = macd_hist.iloc[i]
        
        d_val = round(float(d), 4) if pd.notna(d) else None
        e_val = round(float(e), 4) if pd.notna(e) else None
        m_val = round(float(m), 4) if pd.notna(m) else None
        
        update_data.append((d_val, e_val, m_val, stock_code, trade_dates[i]))
    
    cursor.executemany(
        "UPDATE stock_kline SET dif = ?, dea = ?, macd = ? WHERE stock_code = ? AND trade_date = ?",
        update_data
    )
    conn.commit()
    return len(update_data)


def main():
    print("=" * 60)
    print("MACD 指标补算脚本")
    print("=" * 60)
    
    if not DB_PATH.exists():
        print(f"错误: 数据库文件不存在: {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(str(DB_PATH))
    
    try:
        print("\n[1/3] 检查数据库字段...")
        ensure_columns_exist(conn)
        
        print("\n[2/3] 获取股票列表...")
        stock_codes = get_all_stock_codes(conn)
        total = len(stock_codes)
        print(f"  共 {total} 只股票")
        
        if total == 0:
            print("  没有股票数据，退出")
            return
        
        print(f"\n[3/3] 开始计算 MACD 指标...")
        print("-" * 60)
        
        start_time = time.time()
        success_count = 0
        fail_count = 0
        total_rows = 0
        
        for idx, code in enumerate(stock_codes, 1):
            try:
                n = repair_stock_macd(conn, code)
                total_rows += n
                success_count += 1
            except Exception as e:
                fail_count += 1
                print(f"  ❌ {code} 失败: {e}")
            
            if idx % 100 == 0 or idx == total:
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                eta = (total - idx) / rate if rate > 0 else 0
                print(f"  进度: {idx}/{total} ({idx/total*100:.1f}%) | "
                      f"成功: {success_count} | 失败: {fail_count} | "
                      f"速度: {rate:.1f} 只/秒 | 预计剩余: {eta:.0f}秒")
        
        elapsed = time.time() - start_time
        print("-" * 60)
        print(f"\n✅ 完成！")
        print(f"  股票总数: {total}")
        print(f"  成功: {success_count}")
        print(f"  失败: {fail_count}")
        print(f"  更新K线总数: {total_rows}")
        print(f"  耗时: {elapsed:.1f} 秒")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
