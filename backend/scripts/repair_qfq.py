"""
全量前复权K线数据修复脚本
用法：
  cd backend && python scripts/repair_qfq.py              # 全量修复（100亿市值以上）
  cd backend && python scripts/repair_qfq.py 300502       # 只修复指定股票
功能：
  1. 从腾讯财经重新拉取前复权(qfq)K线数据（400天/页分页拉取）
  2. 全量覆盖更新 stock_kline 表，确保价格是前复权的
  3. 重新计算所有技术指标（MA、布林、MACD等）
  4. 只处理市值100亿以上的股票
  5. 支持断点续传，已处理的股票会跳过
"""
import os
import sys
import time
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "stock.db"
PROGRESS_FILE = PROJECT_ROOT / "data" / "repair_qfq_progress.txt"

from app.services.sync_service import fetch_one_stock_history, _df_to_rows, KLINE_UPSERT_SQL
from app.utils.rate_limiter import RateLimiter

RATE_LIMITER = RateLimiter(3.0)
MIN_MARKET_CAP = 100  # 亿


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_progress(done_codes):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        for code in sorted(done_codes):
            f.write(f"{code}\n")


def get_stocks(conn, target_code=None):
    cursor = conn.cursor()
    
    if target_code:
        cursor.execute("""
            SELECT code, name, total_cap 
            FROM stock_basic 
            WHERE code=? AND is_active=1
        """, (target_code,))
        row = cursor.fetchone()
        if not row:
            return []
        code, name, total_cap = row
        if total_cap and float(total_cap) < MIN_MARKET_CAP:
            print(f"  ⚠️  {code} {name} 市值 {total_cap}亿 < {MIN_MARKET_CAP}亿，跳过")
            return []
        return [(code, name, total_cap)]
    
    cursor.execute("""
        SELECT code, name, total_cap 
        FROM stock_basic 
        WHERE is_active=1 
          AND (code LIKE '0%' OR code LIKE '3%' OR code LIKE '6%')
          AND total_cap IS NOT NULL 
          AND total_cap >= ?
        ORDER BY total_cap DESC
    """, (MIN_MARKET_CAP,))
    return cursor.fetchall()


def get_date_range(conn, stock_code):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MIN(trade_date), MAX(trade_date) 
        FROM stock_kline 
        WHERE stock_code=?
    """, (stock_code,))
    row = cursor.fetchone()
    return row[0], row[1]


def repair_one_stock(conn, stock_code, stock_name, total_cap):
    cursor = conn.cursor()
    
    min_date, max_date = get_date_range(conn, stock_code)
    if not min_date or not max_date:
        print(f"  ⚠️  {stock_code} {stock_name}: 数据库中无数据，跳过")
        return False
    
    cap_str = f"{float(total_cap):.0f}亿" if total_cap else "未知"
    print(f"  拉取 {stock_code} {stock_name} (市值{cap_str}): {min_date} ~ {max_date}")
    
    try:
        df = fetch_one_stock_history(stock_code, min_date, max_date)
        
        if df is None or len(df) == 0:
            print(f"  ⚠️  API无数据返回")
            return False
        
        rows = _df_to_rows(stock_code, df)
        
        cursor.executemany(KLINE_UPSERT_SQL, rows)
        conn.commit()
        
        print(f"  ✓ 更新 {len(rows)} 条K线数据")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    target_code = None
    if len(sys.argv) > 1:
        target_code = sys.argv[1].strip()
    
    print("=" * 60)
    print("前复权K线数据全量修复脚本")
    if target_code:
        print(f"目标股票: {target_code}")
    else:
        print(f"市值筛选: {MIN_MARKET_CAP}亿以上")
    print("=" * 60)
    
    conn = sqlite3.connect(str(DB_PATH))
    
    stocks = get_stocks(conn, target_code)
    
    if not stocks:
        print("\n没有符合条件的股票")
        conn.close()
        return
    
    print(f"\n共 {len(stocks)} 只股票需要处理")
    
    if target_code:
        progress_file = PROGRESS_FILE.with_name(f"repair_qfq_{target_code}_progress.txt")
    else:
        progress_file = PROGRESS_FILE
    
    done_codes = set()
    if progress_file.exists():
        with open(progress_file, 'r', encoding='utf-8') as f:
            done_codes = set(line.strip() for line in f if line.strip())
    
    if done_codes:
        print(f"已完成 {len(done_codes)} 只，剩余 {len(stocks) - len(done_codes)} 只")
        print(f"  从进度文件恢复，跳过已完成的股票")
    
    success_count = 0
    failed_count = 0
    start_time = time.time()
    
    for i, (code, name, total_cap) in enumerate(stocks):
        if code in done_codes:
            continue
        
        print(f"\n[{i+1}/{len(stocks)}] ", end="")
        
        ok = repair_one_stock(conn, code, name, total_cap)
        
        if ok:
            success_count += 1
            done_codes.add(code)
        else:
            failed_count += 1
        
        if (i + 1) % 20 == 0:
            with open(progress_file, 'w', encoding='utf-8') as f:
                for c in sorted(done_codes):
                    f.write(f"{c}\n")
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(stocks) - i - 1) / rate if rate > 0 else 0
            print(f"\n--- 进度: {i+1}/{len(stocks)} | 成功: {success_count} | 失败: {failed_count} | 速度: {rate:.1f}/s | 预计剩余: {eta/60:.1f}分钟 ---")
    
    with open(progress_file, 'w', encoding='utf-8') as f:
        for c in sorted(done_codes):
            f.write(f"{c}\n")
    conn.close()
    
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"全部完成！")
    print(f"  成功: {success_count} 只")
    print(f"  失败: {failed_count} 只")
    print(f"  总耗时: {elapsed/60:.1f} 分钟")
    print(f"{'='*60}")
    
    print(f"\n进度文件: {progress_file}")
    print("如需重新开始，请删除进度文件后再运行")


if __name__ == "__main__":
    main()
