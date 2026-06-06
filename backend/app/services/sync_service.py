import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time
import traceback
import random
import json

from app.utils.database import SessionLocal, engine
from app.models.stock import StockBasic
from app.models.stock_kline import StockKline
from app.models.sync import SyncRecord
from app.services.indicator_service import calculate_all_indicators
from sqlalchemy import and_


REQUEST_DELAY_MIN = 0.1
REQUEST_DELAY_MAX = 0.3


def _get_stock_prefix(code: str) -> str:
    if code.startswith('6'):
        return 'sh'
    else:
        return 'sz'


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
                    except:
                        continue
                
                if (i // batch_size) % 10 == 0:
                    print(f"[INFO] Fetched {i}/{len(all_codes)} codes, found {len(all_stocks)} stocks...")
                    sleep_time = random.uniform(0.1, 0.3)
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


def fetch_one_stock_history(stock_code: str, start_date: str, end_date: str):
    """获取股票历史K线数据（不检查数据库，直接获取全量数据）"""
    from app.api.sync import sync_status
    
    print(f"[INFO] Fetching history for {stock_code} from {start_date} to {end_date}")
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        if sync_status.get("cancelled"):
            print(f"\n[WARN] Fetch cancelled for {stock_code}")
            return pd.DataFrame()
        
        try:
            prefix = _get_stock_prefix(stock_code)
            symbol = f"{prefix}{stock_code}"
            
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start_date},{end_date},1000,qfq"
            
            headers = {"Referer": "https://finance.qq.com"}
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
                print(f"[WARN] No data returned for {stock_code}")
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
            
            df['amount'] = df['volume'] * df['close']
            
            df['dividend_info'] = df['trade_date'].apply(lambda d: dividend_map.get(str(d), None))
            
            df = df.sort_values('trade_date').reset_index(drop=True)
            
            # 计算指标
            df['change_pct'] = ((df['close'] - df['close'].shift(1)) / df['close'].shift(1)) * 100
            df['change_pct'] = df['change_pct'].round(2)
            df['change_pct'] = df['change_pct'].where(df['change_pct'].notna(), None)
            df = calculate_all_indicators(df)
            
            # 计算其他基础指标
            df['amplitude'] = ((df['high'] - df['low']) / df['close'].shift(1)) * 100
            df['turnover_rate'] = df['volume'] / 10000
            
            return df
            
        except Exception as e:
            retry_count += 1
            print(f"[ERROR] Failed to fetch {stock_code} (attempt {retry_count}/{max_retries}): {e}")
            traceback.print_exc()
            
            if retry_count < max_retries:
                wait_time = retry_count * 2
                print(f"[INFO] Waiting {wait_time} seconds before retry...")
                for _ in range(wait_time * 10):
                    if sync_status.get("cancelled"):
                        print(f"\n[WARN] Retry cancelled for {stock_code}")
                        return pd.DataFrame()
                    time.sleep(0.1)
            else:
                print(f"[ERROR] Max retries reached for {stock_code}")
                raise


def save_kline_data(db, stock_code: str, df) -> dict:
    insert_count = 0
    update_count = 0
    
    for _, row in df.iterrows():
        kline = StockKline(
            stock_code=stock_code,
            trade_date=row['trade_date'],
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume']) if pd.notna(row.get('volume')) else None,
            amount=float(row['amount']) / 10000 if pd.notna(row.get('amount')) else None,
            amplitude=float(row['amplitude']) if pd.notna(row.get('amplitude')) else None,
            change_pct=float(row['change_pct']) if pd.notna(row.get('change_pct')) else None,
            turnover_rate=float(row['turnover_rate']) if pd.notna(row.get('turnover_rate')) else None,
            ma5=float(row['MA5']) if pd.notna(row.get('MA5')) else None,
            ma10=float(row['MA10']) if pd.notna(row.get('MA10')) else None,
            ma20=float(row['MA20']) if pd.notna(row.get('MA20')) else None,
            ma30=float(row['MA30']) if pd.notna(row.get('MA30')) else None,
            ma60=float(row['MA60']) if pd.notna(row.get('MA60')) else None,
            ma120=float(row['MA120']) if pd.notna(row.get('MA120')) else None,
            boll_upper=float(row['boll_upper']) if pd.notna(row.get('boll_upper')) else None,
            boll_mid=float(row['boll_mid']) if pd.notna(row.get('boll_mid')) else None,
            boll_lower=float(row['boll_lower']) if pd.notna(row.get('boll_lower')) else None,
            dividend_info=row.get('dividend_info'),
        )
        existing = db.query(StockKline).filter(
            and_(StockKline.stock_code == stock_code, StockKline.trade_date == row['trade_date'])
        ).first()
        if existing:
            existing.open = kline.open
            existing.high = kline.high
            existing.low = kline.low
            existing.close = kline.close
            existing.volume = kline.volume
            existing.amount = kline.amount
            existing.amplitude = kline.amplitude
            existing.change_pct = kline.change_pct
            existing.turnover_rate = kline.turnover_rate
            existing.ma5 = kline.ma5
            existing.ma10 = kline.ma10
            existing.ma20 = kline.ma20
            existing.ma30 = kline.ma30
            existing.ma60 = kline.ma60
            existing.ma120 = kline.ma120
            existing.boll_upper = kline.boll_upper
            existing.boll_mid = kline.boll_mid
            existing.boll_lower = kline.boll_lower
            existing.dividend_info = kline.dividend_info
            update_count += 1
        else:
            db.add(kline)
            insert_count += 1
    db.commit()
    
    return {"insert_count": insert_count, "update_count": update_count}


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
                "failed_stocks": json.loads(latest.failed_stocks) if latest.failed_stocks else [],
                "no_data_stocks": json.loads(latest.no_data_stocks) if latest.no_data_stocks else [],
            }
        return {"sync_date": None, "stock_count": 0, "status": "no_sync", "success_count": 0, "skipped_count": 0, "failed_count": 0, "no_data_count": 0, "failed_stocks": [], "no_data_stocks": []}


def create_sync_record(sync_date: str, stock_count: int, success_count: int = 0, skipped_count: int = 0, failed_count: int = 0, no_data_count: int = 0, failed_stocks: list = None, no_data_stocks: list = None):
    with SessionLocal() as db:
        record = db.query(SyncRecord).filter(SyncRecord.sync_date == sync_date).first()
        if record:
            record.stock_count = stock_count
            record.status = "success"
            record.end_time = datetime.now()
            record.success_count = success_count
            record.skipped_count = skipped_count
            record.failed_count = failed_count
            record.no_data_count = no_data_count
            record.failed_stocks = json.dumps(failed_stocks) if failed_stocks else None
            record.no_data_stocks = json.dumps(no_data_stocks) if no_data_stocks else None
        else:
            record = SyncRecord(
                sync_date=datetime.strptime(sync_date, '%Y-%m-%d').date(),
                stock_count=stock_count,
                status="success",
                end_time=datetime.now(),
                success_count=success_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                no_data_count=no_data_count,
                failed_stocks=json.dumps(failed_stocks) if failed_stocks else None,
                no_data_stocks=json.dumps(no_data_stocks) if no_data_stocks else None,
            )
            db.add(record)
        db.commit()


def run_basic_info_sync():
    """只同步股票基本信息（市值、市盈率等），不同步K线，获取所有股票不跳过"""
    print("=" * 50)
    print("[START] Starting basic info sync task")
    print("=" * 50)
    
    try:
        # 获取所有股票基本信息
        df = fetch_all_stocks_basic_info()
        
        if df is None or len(df) == 0:
            print("[ERROR] Failed to fetch stock basic info")
            return
        
        print(f"[INFO] Fetched {len(df)} stocks basic info")
        
        # 保存到数据库（不跳过任何股票）
        save_stocks_basic_info(df)
        print(f"[DONE] Basic info sync completed, saved {len(df)} stocks")
        
    except Exception as e:
        print(f"[FATAL ERROR] Basic info sync failed: {e}")
        import traceback
        traceback.print_exc()
