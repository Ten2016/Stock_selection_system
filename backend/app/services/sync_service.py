import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
import time
import traceback
import random
import json
import math
from concurrent.futures import CancelledError

from app.utils.database import SessionLocal, engine
from app.models.stock import StockBasic
from app.models.stock_kline import StockKline
from app.models.sync import SyncRecord
from app.services.indicator_service import calculate_all_indicators
from app.utils.sync_state import is_cancelled, end_sync, update_counts, sync_status
from app.utils.rate_limiter import RateLimiter


# 腾讯 K 线 API 全局限流（在 HTTP 请求前 acquire）
KLINE_API_RATE_PER_SECOND = 4.0
_kline_rate_limiter = RateLimiter(KLINE_API_RATE_PER_SECOND)

REQUEST_DELAY_MIN = 0.3
REQUEST_DELAY_MAX = 0.6

# 单次请求的最大返回条数。实测腾讯在 500/640/800 时正常，1000 与 2000 都只回 640 条，
# 3000 以上直接返回空——不要随意调大。
KLINE_PAGE_SIZE = 500

# 向前翻页的页数上限（500 条/页 × 60 页 ≈ 120 年），纯粹作为死循环兜底
MAX_KLINE_PAGES = 60

KLINE_UPSERT_SQL = """
    INSERT INTO stock_kline (
        stock_code, trade_date, open, high, low, close, volume, amount,
        amplitude, change_pct, ma5, ma10, ma20, ma30, ma60,
        boll_upper, boll_mid, boll_lower, dif, dea, macd, dividend_info
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        dif = excluded.dif,
        dea = excluded.dea,
        macd = excluded.macd,
        dividend_info = COALESCE(excluded.dividend_info, stock_kline.dividend_info)
    WHERE (stock_kline.open, stock_kline.high, stock_kline.low, stock_kline.close,
           stock_kline.volume, stock_kline.amount, stock_kline.amplitude, stock_kline.change_pct,
           stock_kline.ma5, stock_kline.ma10, stock_kline.ma20, stock_kline.ma30, stock_kline.ma60,
           stock_kline.boll_upper, stock_kline.boll_mid, stock_kline.boll_lower,
           stock_kline.dif, stock_kline.dea, stock_kline.macd, stock_kline.dividend_info)
       IS NOT
          (excluded.open, excluded.high, excluded.low, excluded.close,
           excluded.volume, excluded.amount, excluded.amplitude, excluded.change_pct,
           excluded.ma5, excluded.ma10, excluded.ma20, excluded.ma30, excluded.ma60,
           excluded.boll_upper, excluded.boll_mid, excluded.boll_lower,
           excluded.dif, excluded.dea, excluded.macd,
           COALESCE(excluded.dividend_info, stock_kline.dividend_info))
"""


def latest_completed_date():
    now = datetime.now(timezone(timedelta(hours=8)))
    return now.date() if now.hour >= 15 else now.date() - timedelta(days=1)


def _get_stock_prefix(code: str) -> str:
    if code.startswith('6'):
        return 'sh'
    else:
        return 'sz'


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    number = float(val)
    return number if math.isfinite(number) else None


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
        if isinstance(val, (dict, list)):
            return val
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
            _safe_float(col(row, 'dif')),
            _safe_float(col(row, 'dea')),
            _safe_float(col(row, 'macd')),
            _format_dividend_info(col(row, 'dividend_info')),
        ))
    return rows


def save_kline_batch(items: List[Tuple[str, pd.DataFrame]]) -> dict:
    """批量 upsert K 线数据，单次事务提交。"""
    if not items:
        return {"row_count": 0, "stock_count": 0}

    row_count = 0
    saved_codes = set()
    with SessionLocal() as db:
        raw_conn = db.connection().connection
        for stock_code, df in items:
            if df is None or df.empty:
                continue
            rows = _df_to_rows(stock_code, df)
            cursor = raw_conn.executemany(KLINE_UPSERT_SQL, rows)
            row_count += cursor.rowcount
            saved_codes.add(stock_code)
        db.commit()

    return {"row_count": row_count, "stock_count": len(saved_codes)}


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
                if is_cancelled():
                    return pd.DataFrame()
                batch = all_codes[i:i+batch_size]
                query = ','.join(batch)
                url = f"https://qt.gtimg.cn/q={query}"
                
                headers = {"Referer": "https://finance.qq.com"}
                response = requests.get(url, headers=headers, timeout=15)
                response.encoding = 'gbk'
                
                response.raise_for_status()
                
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
                        price = _optional_float(parts[3]) or 0
                        
                        if not code or not name or price <= 0:
                            continue
                        
                        market_cap_yi = _optional_float(parts[45]) or 0
                        pe_ratio = _optional_float(parts[52]) if len(parts) > 52 else None
                        pe_ratio_static = _optional_float(parts[53]) if len(parts) > 53 else None
                        pb_ratio = _optional_float(parts[46])
                        ytd_change_pct = _optional_float(parts[62]) if len(parts) > 62 else None
                        
                        if market_cap_yi > 0:
                            all_stocks.append({
                                '代码': code,
                                '名称': name,
                                '总市值': market_cap_yi,
                                '流通市值': _optional_float(parts[44]),
                                '市盈率': pe_ratio,
                                '静态市盈率': pe_ratio_static,
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
            
            print(f"[INFO] Fetched {len(df)} stocks from Tencent Finance")
            return df
            
        except Exception as e:
            retry_count += 1
            print(f"[ERROR] Failed to fetch stocks basic info (attempt {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                wait_time = retry_count * 3
                print(f"[INFO] Waiting {wait_time} seconds before retry...")
                for _ in range(wait_time * 10):
                    if is_cancelled():
                        return pd.DataFrame()
                    time.sleep(0.1)
            else:
                print(f"[ERROR] Max retries reached for stocks basic info")
                traceback.print_exc()
                raise


def _optional_float(val) -> Optional[float]:
    """空值 / NaN 统一转 None，避免把 NaN 写进 DECIMAL 列。"""
    if val is None or pd.isna(val):
        return None
    try:
        number = float(val)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def save_stocks_basic_info(df):
    with SessionLocal() as db:
        # 一次性载入现有记录，避免逐行 SELECT（约 5000 行 → 5000 次查询）
        existing_map = {s.code: s for s in db.query(StockBasic).all()}

        for _, row in df.iterrows():
            code = row['代码']
            stock = existing_map.get(code)
            if stock is None:
                stock = StockBasic(code=code, market='SSE' if code.startswith('6') else 'SZSE')
                db.add(stock)

            stock.name = row['名称']
            stock.total_cap = _optional_float(row['总市值'])
            stock.pe_ratio = _optional_float(row.get('市盈率'))
            stock.pe_ratio_static = _optional_float(row.get('静态市盈率'))
            stock.pb_ratio = _optional_float(row.get('市净率'))
            stock.ytd_change_pct = _optional_float(row.get('今年涨跌幅'))

        db.commit()


def _fetch_kline_page(symbol: str, start_date: str, end_date: str, count: int = None) -> list:
    """单次请求腾讯K线接口，返回原始kline列表（带限流和重试）。"""
    count = count or KLINE_PAGE_SIZE
    max_retries = 3
    for retry_count in range(max_retries):
        if is_cancelled():
            raise CancelledError()

        try:
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start_date},{end_date},{count},qfq"

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
            
            if not isinstance(stock_data, dict):
                raise ValueError('K线响应格式错误')
            klines = stock_data.get('qfqday', stock_data.get('day', []))
            if not isinstance(klines, list):
                raise ValueError('K线响应格式错误')
            return klines
            
        except Exception as e:
            if retry_count < max_retries - 1:
                wait_time = (retry_count + 1) * 2
                for _ in range(wait_time * 10):
                    if is_cancelled():
                        raise CancelledError()
                    time.sleep(0.1)
            else:
                raise
    return []


def _fetch_kline_paged(symbol: str, start_dt, end_dt) -> list:
    """从 end_dt 向前翻页拉满 [start_dt, end_dt]，返回原始 kline 列表。

    腾讯接口的语义是「返回区间内数据，但最多 count 条；超出时从 end 往回截断」——
    即请求 10 年只会拿到最后 500 条，早期数据被静默丢弃。所以不能按固定日历窗口
    切页（页内交易日数一旦超过 count 就会缺口且无任何报错），必须用**上一页实际
    返回的最早日期**决定下一页的终点，这样无论交易日疏密都不会漏。
    """
    all_klines = []
    cursor_end = end_dt

    for _ in range(MAX_KLINE_PAGES):
        if is_cancelled():
            raise CancelledError()
        if cursor_end < start_dt:
            break

        page = _fetch_kline_page(
            symbol, start_dt.strftime("%Y-%m-%d"), cursor_end.strftime("%Y-%m-%d")
        )
        if not page:
            break

        try:
            dates = [datetime.strptime(row[0], "%Y-%m-%d").date() for row in page]
        except (ValueError, IndexError, TypeError):
            raise ValueError(f'{symbol} K线分页包含无效日期')
        if any(day < start_dt or day > cursor_end for day in dates):
            raise ValueError(f'{symbol} K线分页返回了区间外数据')
        all_klines.extend(page)
        earliest = min(dates)

        # 已回溯到请求起点，或本页未被截断（说明区间已取完）
        if earliest <= start_dt or len(page) < KLINE_PAGE_SIZE:
            break

        cursor_end = earliest - timedelta(days=1)
    else:
        raise ValueError(f'{symbol} 分页超过 {MAX_KLINE_PAGES} 页，未保存不完整历史')

    return all_klines


def fetch_one_stock_history(stock_code: str, start_date: str, end_date: str, history_data: list = None):
    """获取股票历史 K 线数据（自 end_date 向前分页拉取，见 _fetch_kline_paged）。"""
    if '-' not in start_date:
        start_date_clean = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    else:
        start_date_clean = start_date
    if '-' not in end_date:
        end_date_clean = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
    else:
        end_date_clean = end_date
    
    prefix = _get_stock_prefix(stock_code)
    symbol = f"{prefix}{stock_code}"
    
    start_dt = datetime.strptime(start_date_clean, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date_clean, "%Y-%m-%d").date()

    all_klines = _fetch_kline_paged(symbol, start_dt, end_dt)

    if not all_klines:
        return pd.DataFrame()
    
    dividend_map = {}
    base_klines = []
    
    seen_dates = set()
    for row in all_klines:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            raise ValueError(f'{stock_code} K线字段不足')
        trade_date = row[0]
        if trade_date in seen_dates:
            continue
        seen_dates.add(trade_date)
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
    
    for name in ('open', 'close', 'high', 'low', 'volume'):
        if not df[name].map(lambda value: pd.notna(value) and math.isfinite(value)).all():
            raise ValueError(f'{stock_code} K线 {name} 包含无效数值')
    if (df['high'] < df['low']).any() or (df['volume'] < 0).any():
        raise ValueError(f'{stock_code} K线价格或成交量无效')
    # 此接口未提供成交额，不能用前复权收盘价乘成交量替代。
    df['amount'] = None
    
    df['dividend_info'] = df['trade_date'].apply(lambda d: dividend_map.get(str(d), None))
    
    df = df.sort_values('trade_date').reset_index(drop=True)
    
    if history_data:
        history_df = pd.DataFrame(history_data)
        history_df['trade_date'] = pd.to_datetime(history_df['trade_date']).dt.date
        history_df = history_df[history_df['trade_date'] < df['trade_date'].min()]
        
        combined_df = pd.concat([
            history_df[['trade_date', 'close']],
            df[['trade_date', 'close', 'open', 'high', 'low', 'volume', 'amount', 'dividend_info']]
        ], ignore_index=True)
        
        combined_df = combined_df.drop_duplicates('trade_date', keep='last').sort_values('trade_date').reset_index(drop=True)
        
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


# 小于报价精度，确保 1 分钱的历史价格变化也会触发重拉。
QFQ_DRIFT_TOLERANCE = 0.005


def detect_qfq_drift(df: pd.DataFrame, existing_closes: Dict[Any, float]) -> Optional[str]:
    """比对新数据与库中同一交易日的前复权收盘价。

    除权除息后，腾讯会用新的复权因子重算**全部**历史价格，因此重叠日期的收盘价
    会整体变化。检测到变化说明库里的历史数据已按旧因子失效，必须全量重拉。
    返回差异描述；无差异返回 None。
    """
    if df is None or len(df) == 0 or not existing_closes:
        return None

    for row in df.itertuples(index=False):
        old_close = existing_closes.get(row.trade_date)
        if old_close is None:
            continue
        new_close = getattr(row, 'close', None)
        if new_close is None or pd.isna(new_close):
            continue
        if abs(float(new_close) - float(old_close)) > QFQ_DRIFT_TOLERANCE:
            return f"{row.trade_date} 收盘价 {float(old_close)} → {float(new_close)}"
    return None


def get_latest_sync_date() -> Optional[str]:
    with SessionLocal() as db:
        record = db.query(SyncRecord).order_by(SyncRecord.sync_date.desc()).first()
        if record:
            return record.sync_date.strftime('%Y-%m-%d')
    return None


def get_sync_status() -> Dict[str, Any]:
    with SessionLocal() as db:
        latest = db.query(SyncRecord).order_by(SyncRecord.end_time.desc(), SyncRecord.id.desc()).first()
        if latest:
            return {
                "sync_date": latest.sync_date.strftime('%Y-%m-%d'),
                "stock_count": latest.stock_count,
                "status": latest.status,
                "error_msg": latest.error_msg,
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
    status: str = "success", error_msg: str = None,
):
    with SessionLocal() as db:
        sync_date_clean = sync_date.replace('-', '')
        sync_date_obj = datetime.strptime(sync_date_clean, '%Y%m%d').date()
        
        record = db.query(SyncRecord).filter(SyncRecord.sync_date == sync_date_obj).first()
        if record:
            record.stock_count = stock_count
            record.status = status
            record.error_msg = error_msg
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
                status=status,
                error_msg=error_msg,
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
    error_msg = None
    try:
        df = fetch_all_stocks_basic_info()
        if is_cancelled():
            return
        if df is None or len(df) == 0:
            raise ValueError('未获取到股票基本信息')
        save_stocks_basic_info(df)
        update_counts(len(df), 0, [], [], 100)
        print(f"[DONE] Basic info sync completed, saved {len(df)} stocks")
    except Exception as exc:
        error_msg = str(exc)
        traceback.print_exc()
    finally:
        end_sync(error_msg)


def run_repair_indicators():
    """修复所有股票的K线指标数据：从数据库读取全部K线，重新计算指标后回写"""
    from app.services.indicator_service import calculate_all_indicators
    from app.utils.data_migrations import repair_json_columns

    print("=" * 50)
    print("[START] Starting repair indicators task")
    print("=" * 50)

    error_msg = None
    try:
        if is_cancelled():
            return
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
                        'volume': float(k.volume) if k.volume is not None else None,
                    })

                df = pd.DataFrame(rows)
                df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
                df = df.sort_values('trade_date').reset_index(drop=True)

                record_count = len(df)

                # 重新计算指标
                df['change_pct'] = ((df['close'] - df['close'].shift(1)) / df['close'].shift(1)) * 100
                df['change_pct'] = df['change_pct'].round(2)
                df['change_pct'] = df['change_pct'].where(df['change_pct'].notna(), None)
                df = calculate_all_indicators(df)
                df['amplitude'] = ((df['high'] - df['low']) / df['close'].shift(1)) * 100

                indicator_columns = (
                    'MA5', 'MA10', 'MA20', 'MA30', 'MA60', 'boll_upper', 'boll_mid',
                    'boll_lower', 'dif', 'dea', 'macd', 'change_pct', 'amplitude',
                )
                updates = [
                    {'id': kline.id, **{name.lower(): _safe_float(row[name]) for name in indicator_columns}}
                    for kline, (_, row) in zip(klines, df.iterrows())
                ]
                db.bulk_update_mappings(StockKline, updates)
                db.commit()
                repaired += 1

                print(f"[OK] [{idx + 1}/{total}] {code} repaired {record_count} records")
                sync_status["progress"] = 20 + int(((idx + 1) / total) * 70) if total else 100
                update_counts(idx + 1, 0, [], [], sync_status["progress"])

            print(f"\n[DONE] Repair completed! Repaired {repaired} stocks")

    except Exception as e:
        error_msg = str(e)
        print(f"[FATAL ERROR] Repair indicators failed: {e}")
        traceback.print_exc()
    finally:
        end_sync(error_msg)
