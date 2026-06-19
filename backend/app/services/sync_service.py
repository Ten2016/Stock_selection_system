import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import time
import traceback
import random
import json

from app.utils.database import SessionLocal, engine
from app.models.stock import StockBasic
from app.models.stock_kline import StockKline
from app.models.sync import SyncRecord
from app.services.indicator_service import calculate_all_indicators
from app.utils.sync_state import is_cancelled
from app.utils.rate_limiter import RateLimiter


# 腾讯 K 线 API 全局限流（在 HTTP 请求前 acquire）
KLINE_API_RATE_PER_SECOND = 4.0
_kline_rate_limiter = RateLimiter(KLINE_API_RATE_PER_SECOND)

REQUEST_DELAY_MIN = 0.3
REQUEST_DELAY_MAX = 0.6

KLINE_UPSERT_SQL = """
    INSERT INTO stock_kline (
        stock_code, trade_date, open, high, low, close, volume, amount,
        amplitude, change_pct, ma5, ma10, ma20, ma30, ma60,
        boll_upper, boll_mid, boll_lower, dividend_info
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(stock_code, trade_date) DO UPDATE SET
        open = excluded.open,
        high = excluded.high,
        low = excluded.low,
        close = excluded.close,
        volume = excluded.volume,
        amount = excluded.amount,
        amplitude = excluded.amplitude,
        change_pct = excluded.change_pct,
        ma5 = excluded.ma5,
        ma10 = excluded.ma10,
        ma20 = excluded.ma20,
        ma30 = excluded.ma30,
        ma60 = excluded.ma60,
        boll_upper = excluded.boll_upper,
        boll_mid = excluded.boll_mid,
        boll_lower = excluded.boll_lower,
        dividend_info = excluded.dividend_info
"""


def _get_stock_prefix(code: str) -> str:
    if code.startswith('6'):
        return 'sh'
    else:
        return 'sz'


def _safe_float(val) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return float(val)


def _format_dividend_info(val) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, str):
        return val
    return json.dumps(val, ensure_ascii=False)


def _df_to_rows(stock_code: str, df: pd.DataFrame) -> List[tuple]:
    rows = []
    col_index = {name: idx for idx, name in enumerate(df.columns)}
    values = df.values

    def col(row, name):
        idx = col_index.get(name)
        if idx is None:
            return None
        val = row[idx]
        if pd.isna(val):
            return None
        return val

    for row in values:
        amount = col(row, 'amount')
        rows.append((
            stock_code,
            col(row, 'trade_date'),
            _safe_float(col(row, 'open')),
            _safe_float(col(row, 'high')),
            _safe_float(col(row, 'low')),
            _safe_float(col(row, 'close')),
            _safe_float(col(row, 'volume')),
            _safe_float(amount) / 10000 if amount is not None else None,
            _safe_float(col(row, 'amplitude')),
            _safe_float(col(row, 'change_pct')),
            _safe_float(col(row, 'MA5')),
            _safe_float(col(row, 'MA10')),
            _safe_float(col(row, 'MA20')),
            _safe_float(col(row, 'MA30')),
            _safe_float(col(row, 'MA60')),
            _safe_float(col(row, 'boll_upper')),
            _safe_float(col(row, 'boll_mid')),
            _safe_float(col(row, 'boll_lower')),
            _format_dividend_info(col(row, 'dividend_info')),
        ))
    return rows


def save_kline_batch(items: List[Tuple[str, pd.DataFrame]]) -> dict:
    """批量 upsert K 线数据，单次事务提交。"""
    if not items:
        return {"row_count": 0, "stock_count": 0}

    all_rows = []
    for stock_code, df in items:
        if df is None or len(df) == 0:
            continue
        all_rows.extend(_df_to_rows(stock_code, df))

    if not all_rows:
        return {"row_count": 0, "stock_count": 0}

    with SessionLocal() as db:
        raw_conn = db.connection().connection
        raw_conn.executemany(KLINE_UPSERT_SQL, all_rows)
        db.commit()

    return {"row_count": len(all_rows), "stock_count": len(items)}


def save_kline_data(db, stock_code: str, df) -> dict:
    """单只股票 upsert（兼容旧调用，内部仍走批量 upsert）。"""
    result = save_kline_batch([(stock_code, df)])
    return {"insert_count": result["row_count"], "update_count": 0}


def fetch_all_stocks_basic_info():
    print("[INFO] Fetching all stocks basic info from Tencent Finance...")
    
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print(f"[INFO] Attempt {retry_count + 1}/{max_retries} to fetch stocks basic info...")
            
            all_stocks = []
            
            # 上海：600/601/603/605主板 + 688科创板
            sh_codes = []
            for prefix in ['600', '601', '603', '605']:
                sh_codes.extend([f"sh{prefix}{str(i).zfill(3)}" for i in range(1000)])
            sh_codes.extend([f"sh688{str(i).zfill(3)}" for i in range(1000)])
            
            # 深圳：000/001/002/003主板 + 300/301创业板
            sz_codes = []
            for prefix in ['000', '001', '002', '003']:
                sz_codes.extend([f"sz{prefix}{str(i).zfill(3)}" for i in range(1000)])
            for prefix in ['300', '301']:
                sz_codes.extend([f"sz{prefix}{str(i).zfill(3)}" for i in range(1000)])
            
            all_codes = sh_codes + sz_codes
            
            batch_size = 50
            for i in range(0, len(all_codes), batch_size):
                batch = all_codes[i:i+batch_size]
                query = ','.join(batch)
                url = f"https://qt.gtimg.cn/q={query}"
                
                headers = {"Referer": "https://finance.qq.com"}
                response = requests.get(url, headers=headers, timeout=15)
                response.encoding = 'gbk'
                
                if response.status_code != 200:
                    continue
                
                lines = response.text.strip().split('\n')
                
                for line in lines:
                    if '=' not in line:
                        continue
                    parts = line.split('~')
                    if len(parts) < 50:
                        continue
                    
                    try:
                        code = parts[2]
                        name = parts[1]
                        price = float(parts[3]) if parts[3] else 0
                        
                        if not code or not name or price <= 0:
                            continue
                        
                        market_cap_yi = float(parts[45]) if len(parts) > 45 and parts[45] else 0
                        pe_ratio = float(parts[39]) if len(parts) > 39 and parts[39] else None
                        pb_ratio = float(parts[46]) if len(parts) > 46 and parts[46] else None
                        ytd_change_pct = float(parts[32]) if len(parts) > 32 and parts[32] else None
                        
                        if market_cap_yi > 0:
                            all_stocks.append({
                                '代码': code,
                                '名称': name,
                                '总市值': int(market_cap_yi),
                                '流通市值': int(market_cap_yi * 0.8),
                                '市盈率': pe_ratio,
                                '市净率': pb_ratio,
                                '今年涨跌幅': ytd_change_pct,
                            })
                    except Exception:
                        continue
                
                if (i // batch_size) % 10 == 0:
                    print(f"[INFO] Fetched {i}/{len(all_codes)} codes, found {len(all_stocks)} stocks...")
                    sleep_time = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
                    time.sleep(sleep_time)
            
            if not all_stocks:
                raise Exception("No stocks fetched")
            
            df = pd.DataFrame(all_stocks)
            df = df.drop_duplicates(subset=['代码'], keep='first')
            df = df.dropna(subset=['总市值'])
            df = df.dropna(subset=['流通市值'])
            
            print(f"[INFO] Fetched {len(df)} stocks from Tencent Finance")
            return df
            
        except Exception as e:
            retry_count += 1
            print(f"[ERROR] Failed to fetch stocks basic info (attempt {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                wait_time = retry_count * 3
                print(f"[INFO] Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                print(f"[ERROR] Max retries reached for stocks basic info")
                traceback.print_exc()
                raise


def save_stocks_basic_info(df):
    with SessionLocal() as db:
        for _, row in df.iterrows():
            existing = db.query(StockBasic).filter(StockBasic.code == row['代码']).first()
            if existing:
                existing.name = row['名称']
                existing.total_cap = float(row['总市值'])
                existing.pe_ratio = float(row['市盈率']) if row.get('市盈率') else None
                existing.pb_ratio = float(row['市净率']) if row.get('市净率') else None
                existing.ytd_change_pct = float(row['今年涨跌幅']) if row.get('今年涨跌幅') else None
            else:
                stock = StockBasic(
                    code=row['代码'],
                    name=row['名称'],
                    market='SSE' if row['代码'].startswith('6') else 'SZSE',
                    total_cap=float(row['总市值']),
                    pe_ratio=float(row['市盈率']) if row.get('市盈率') else None,
                    pb_ratio=float(row['市净率']) if row.get('市净率') else None,
                    ytd_change_pct=float(row['今年涨跌幅']) if row.get('今年涨跌幅') else None,
                )
                db.add(stock)
        db.commit()


def fetch_one_stock_history(stock_code: str, start_date: str, end_date: str, history_data: list = None):
    """获取股票历史 K 线数据（请求前全局限流）。"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        if is_cancelled():
            return pd.DataFrame()
        
        try:
            prefix = _get_stock_prefix(stock_code)
            symbol = f"{prefix}{stock_code}"
            
            if '-' not in start_date:
                start_date_clean = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            else:
                start_date_clean = start_date
            if '-' not in end_date:
                end_date_clean = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
            else:
                end_date_clean = end_date
            
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start_date_clean},{end_date_clean},1000,qfq"
            
            headers = {"Referer": "https://finance.qq.com"}
            _kline_rate_limiter.acquire()
            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")
            
            data = response.json()
            
            if data.get('code') != 0:
                raise Exception(f"API error: {data.get('msg')}")
            
            raw_data = data.get('data', {})
            
            if isinstance(raw_data, list):
                if len(raw_data) > 0:
                    stock_data = raw_data[0] if isinstance(raw_data[0], dict) else {}
                else:
                    stock_data = {}
            elif isinstance(raw_data, dict):
                stock_data = raw_data.get(symbol, {})
            else:
                stock_data = {}
            
            klines = stock_data.get('qfqday', stock_data.get('day', [])) if isinstance(stock_data, dict) else []
            
            if not klines:
                return pd.DataFrame()
            
            dividend_map = {}
            base_klines = []
            
            for row in klines:
                trade_date = row[0]
                if len(row) >= 7 and isinstance(row[6], dict):
                    dividend_map[trade_date] = row[6]
                base_klines.append(row[:6])
            
            df = pd.DataFrame(base_klines, columns=['trade_date', 'open', 'close', 'high', 'low', 'volume'])
            
            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            
            df['amount'] = df['volume'] * df['close'] / 100
            
            df['dividend_info'] = df['trade_date'].apply(lambda d: dividend_map.get(str(d), None))
            
            df = df.sort_values('trade_date').reset_index(drop=True)
            
            if history_data:
                history_df = pd.DataFrame(history_data)
                history_df['trade_date'] = pd.to_datetime(history_df['trade_date'])
                
                combined_df = pd.concat([
                    history_df[['trade_date', 'close']],
                    df[['trade_date', 'close', 'open', 'high', 'low', 'volume', 'amount', 'dividend_info']]
                ], ignore_index=True)
                
                combined_df['change_pct'] = (
                    (combined_df['close'] - combined_df['close'].shift(1)) / combined_df['close'].shift(1)
                ) * 100
                combined_df['change_pct'] = combined_df['change_pct'].round(2)
                combined_df['change_pct'] = combined_df['change_pct'].where(combined_df['change_pct'].notna(), None)
                combined_df = calculate_all_indicators(combined_df)
                
                combined_df['amplitude'] = (
                    (combined_df['high'] - combined_df['low']) / combined_df['close'].shift(1)
                ) * 100
                
                new_dates = set(df['trade_date'])
                df = combined_df[combined_df['trade_date'].isin(new_dates)].reset_index(drop=True)
            else:
                df['change_pct'] = ((df['close'] - df['close'].shift(1)) / df['close'].shift(1)) * 100
                df['change_pct'] = df['change_pct'].round(2)
                df['change_pct'] = df['change_pct'].where(df['change_pct'].notna(), None)
                df = calculate_all_indicators(df)
                df['amplitude'] = ((df['high'] - df['low']) / df['close'].shift(1)) * 100
            
            return df
            
        except Exception as e:
            retry_count += 1
            print(f"[ERROR] Failed to fetch {stock_code} (attempt {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                wait_time = retry_count * 2
                for _ in range(wait_time * 10):
                    if is_cancelled():
                        return pd.DataFrame()
                    time.sleep(0.1)
            else:
                raise


def get_latest_sync_date() -> Optional[str]:
    with SessionLocal() as db:
        record = db.query(SyncRecord).order_by(SyncRecord.sync_date.desc()).first()
        if record:
            return record.sync_date.strftime('%Y-%m-%d')
    return None


def get_sync_status() -> Dict[str, Any]:
    with SessionLocal() as db:
        latest = db.query(SyncRecord).order_by(SyncRecord.sync_date.desc()).first()
        if latest:
            return {
                "sync_date": latest.sync_date.strftime('%Y-%m-%d'),
                "stock_count": latest.stock_count,
                "status": latest.status,
                "success_count": latest.success_count,
                "skipped_count": latest.skipped_count,
                "failed_count": latest.failed_count,
                "no_data_count": latest.no_data_count,
                "failed_stocks": latest.failed_stocks or [],
                "no_data_stocks": latest.no_data_stocks or [],
            }
        return {
            "sync_date": None, "stock_count": 0, "status": "no_sync",
            "success_count": 0, "skipped_count": 0, "failed_count": 0,
            "no_data_count": 0, "failed_stocks": [], "no_data_stocks": [],
        }


def create_sync_record(
    sync_date: str, stock_count: int, success_count: int = 0,
    skipped_count: int = 0, failed_count: int = 0, no_data_count: int = 0,
    failed_stocks: list = None, no_data_stocks: list = None,
):
    with SessionLocal() as db:
        sync_date_clean = sync_date.replace('-', '')
        sync_date_obj = datetime.strptime(sync_date_clean, '%Y%m%d').date()
        
        record = db.query(SyncRecord).filter(SyncRecord.sync_date == sync_date_obj).first()
        if record:
            record.stock_count = stock_count
            record.status = "success"
            record.end_time = datetime.now()
            record.success_count = success_count
            record.skipped_count = skipped_count
            record.failed_count = failed_count
            record.no_data_count = no_data_count
            record.failed_stocks = failed_stocks
            record.no_data_stocks = no_data_stocks
        else:
            record = SyncRecord(
                sync_date=sync_date_obj,
                stock_count=stock_count,
                status="success",
                end_time=datetime.now(),
                success_count=success_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                no_data_count=no_data_count,
                failed_stocks=failed_stocks,
                no_data_stocks=no_data_stocks,
            )
            db.add(record)
        db.commit()


def run_basic_info_sync():
    """只同步股票基本信息（市值、市盈率等），不同步K线，获取所有股票不跳过"""
    print("=" * 50)
    print("[START] Starting basic info sync task")
    print("=" * 50)
    
    try:
        df = fetch_all_stocks_basic_info()
        
        if df is None or len(df) == 0:
            print("[ERROR] Failed to fetch stock basic info")
            return
        
        print(f"[INFO] Fetched {len(df)} stocks basic info")
        save_stocks_basic_info(df)
        print(f"[DONE] Basic info sync completed, saved {len(df)} stocks")
        
    except Exception as e:
        print(f"[FATAL ERROR] Basic info sync failed: {e}")
        traceback.print_exc()


def run_repair_indicators():
    """修复所有股票的K线指标数据：从数据库读取全部K线，重新计算指标后回写"""
    from app.services.indicator_service import calculate_all_indicators
    from app.utils.data_migrations import repair_json_columns

    print("=" * 50)
    print("[START] Starting repair indicators task")
    print("=" * 50)

    begin_sync()
    try:
        # 第一步：修复 JSON 格式数据
        print("\n[STEP 1/2] Repairing JSON-like data...")
        with engine.begin() as conn:
            repaired_json = repair_json_columns(conn)
        print(f"[INFO] JSON repair done: {repaired_json}")

        # 第二步：重新计算所有股票的指标
        print("\n[STEP 2/2] Recalculating indicators for all stocks...")
        with SessionLocal() as db:
            # 获取所有有K线数据的股票代码
            stock_codes = db.query(StockKline.stock_code).distinct().all()
            stock_codes = [s[0] for s in stock_codes]
            total = len(stock_codes)
            print(f"[INFO] Found {total} stocks with K-line data")

            repaired = 0
            for idx, code in enumerate(stock_codes):
                if is_cancelled():
                    print("\n[WARN] Repair cancelled by user")
                    break

                # 按日期升序取出全部K线
                klines = db.query(StockKline).filter(
                    StockKline.stock_code == code
                ).order_by(StockKline.trade_date.asc()).all()

                if not klines:
                    continue

                # 转为 DataFrame
                rows = []
                for k in klines:
                    rows.append({
                        'trade_date': k.trade_date,
                        'open': float(k.open),
                        'close': float(k.close),
                        'high': float(k.high),
                        'low': float(k.low),
                        'volume': float(k.volume) if k.volume else None,
                    })

                df = pd.DataFrame(rows)
                df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
                df = df.sort_values('trade_date').reset_index(drop=True)

                # 重新计算指标
                df['amount'] = df['volume'] * df['close'] / 100
                df['change_pct'] = ((df['close'] - df['close'].shift(1)) / df['close'].shift(1)) * 100
                df['change_pct'] = df['change_pct'].round(2)
                df['change_pct'] = df['change_pct'].where(df['change_pct'].notna(), None)
                df = calculate_all_indicators(df)
                df['amplitude'] = ((df['high'] - df['low']) / df['close'].shift(1)) * 100

                # 批量 upsert 回数据库
                save_kline_batch([(code, df)])
                repaired += 1

                if (idx + 1) % 100 == 0 or idx + 1 == total:
                    print(f"[INFO] Repaired {idx + 1}/{total} stocks")
                    sync_status["progress"] = 20 + int(((idx + 1) / total) * 70) if total else 100
                    update_counts(idx + 1, 0, [], [], sync_status["progress"])

            print(f"\n[DONE] Repair completed! Repaired {repaired} stocks")

    except Exception as e:
        print(f"[FATAL ERROR] Repair indicators failed: {e}")
        traceback.print_exc()
    finally:
        end_sync()
