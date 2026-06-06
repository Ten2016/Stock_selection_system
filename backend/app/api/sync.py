import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
from pydantic import BaseModel

from app.utils.database import get_db
from app.utils.response import success, error
from app.services import sync_service, stock_service
from datetime import datetime, timedelta

router = APIRouter()


sync_status = {"is_syncing": False, "progress": 0, "cancelled": False, "success_count": 0, "failed_count": 0, "skipped_count": 0, "no_data_count": 0, "failed_stocks": [], "no_data_stocks": []}


class SyncRequest(BaseModel):
    start_date: str
    end_date: str


def process_single_stock(stock, start_date, end_date, skipped_codes, existing_dates_cache, skip_info_cache, skip_check=True, only_skip_list=False):
    """处理单个股票的函数，用于并发执行
    
    Args:
        stock: 股票对象
        start_date: 开始日期
        end_date: 结束日期
        skipped_codes: 跳过列表
        existing_dates_cache: 预先加载的现有日期缓存 {stock_code: set(dates)}
        skip_info_cache: 预先加载的跳过信息缓存 {stock_code: (should_skip, reason)}
        skip_check: 是否检查跳过列表（默认True）
        only_skip_list: 是否只检查跳过列表，不检查 should_skip_stock（近10天同步时为True）
    """
    stock_code = stock.code
    stock_name = stock.name
    result = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "status": "pending",
        "reason": None,
        "kline_data": None
    }
    
    try:
        # 检查是否在跳过列表中（仅当需要检查时）
        if skip_check:
            from app.utils.skipped_stocks import is_skipped
            if is_skipped(stock_code, cached_codes=skipped_codes):
                result["status"] = "skipped"
                result["reason"] = "在跳过列表中"
                return result
        
        # 检查是否应该跳过（仅当需要检查且 not only_skip_list 时）
        if skip_check and not only_skip_list:
            # 从缓存获取跳过信息（避免重复查询数据库）
            if stock_code in skip_info_cache:
                should_skip, reason = skip_info_cache[stock_code]
                if should_skip:
                    result["status"] = "skipped"
                    result["reason"] = reason
                    return result
        
        # 从缓存获取现有数据（避免重复查询数据库）
        existing_dates = existing_dates_cache.get(stock_code, set())
        
        # 抓取新数据
        from app.services import sync_service
        kline_data = sync_service.fetch_one_stock_history_with_db(stock_code, start_date, end_date, existing_dates)
        
        if len(kline_data) > 0:
            result["status"] = "success"
            result["kline_data"] = kline_data
        else:
            result["status"] = "no_data"
            result["reason"] = "no data available"
        
        # 每个请求完成后，在工作线程中随机等待100-300毫秒
        sleep_time = random.uniform(0.1, 0.3)
        time.sleep(sleep_time)
        
    except Exception as e:
        result["status"] = "failed"
        result["reason"] = str(e)
        import traceback
        traceback.print_exc()
    
    return result


def run_sync_task(start_date: str, end_date: str, skip_check: bool = True, only_skip_list: bool = False):
    """运行同步任务
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        skip_check: 是否检查跳过列表（默认True）
        only_skip_list: 是否只检查跳过列表，不检查 should_skip_stock（近10天同步时为True）
    """
    global sync_status
    # 在函数最开始初始化所有变量，避免作用域问题
    count = 0
    success_count = 0
    failed_stocks = []
    no_data_stocks = []
    skipped_count = 0
    total = 0
    lock = threading.Lock()
    
    try:
        sync_status["is_syncing"] = True
        sync_status["progress"] = 0
        sync_status["cancelled"] = False
        
        print("=" * 50)
        print("[START] Starting sync task")
        print(f"[INFO] Date range: {start_date} to {end_date}")
        print(f"[INFO] Concurrent requests: 100")
        if only_skip_list:
            print(f"[INFO] Mode: Only skip list check (skip excluded stocks, sync all others)")
        else:
            print(f"[INFO] Skip check: {'enabled' if skip_check else 'disabled'}")
        print("[INFO] Press Ctrl+C to cancel sync")
        print("=" * 50)
        
        print("\n[STEP 1/3] Loading stocks from database...")
        from app.services.stock_service import get_stock_list
        from app.utils.database import SessionLocal
        with SessionLocal() as db_list:
            all_stocks, _ = get_stock_list(db_list, skip=0, limit=10000)
        
        # 筛选股票并按市值从大到小排序
        filtered_stocks = [s for s in all_stocks if s.code.startswith(('0', '3', '6'))]
        # 确保按市值降序排序
        filtered_stocks.sort(key=lambda x: x.total_cap if x.total_cap else 0, reverse=True)
        
        total = len(filtered_stocks)
        print(f"[INFO] Loaded {total} stocks (filtered from {len(all_stocks)}), sorted by market cap descending")
        
        sync_status["progress"] = 20
        
        print("\n[STEP 2/3] Syncing K-line data...")
        count = 0
        success_count = 0
        failed_stocks = []
        no_data_stocks = []
        skipped_count = 0
        
        sync_status["success_count"] = 0
        sync_status["failed_count"] = 0
        sync_status["skipped_count"] = 0
        sync_status["no_data_count"] = 0
        sync_status["failed_stocks"] = []
        sync_status["no_data_stocks"] = []
        
        # 加载跳过的股票列表（只读一次）
        from app.utils.skipped_stocks import load_skipped_codes
        skipped_codes = load_skipped_codes()
        print(f"[INFO] Loaded {len(skipped_codes)} stocks from skip list")
        
        # 预先加载所有股票的现有日期到缓存（避免每个线程都查询数据库）
        print("[INFO] Pre-loading existing dates cache...")
        existing_dates_cache = {}
        with SessionLocal() as db:
            from app.models import StockKline
            from sqlalchemy import func
            # 批量查询所有股票的现有日期
            results = db.query(StockKline.stock_code, func.group_concat(StockKline.trade_date)).group_by(StockKline.stock_code).all()
            for stock_code, dates_str in results:
                if dates_str:
                    existing_dates_cache[stock_code] = set(dates_str.split(','))
        print(f"[INFO] Cached existing dates for {len(existing_dates_cache)} stocks")
        
        # 预先加载跳过信息缓存（避免每个线程都查询数据库）
        print("[INFO] Pre-loading skip info cache...")
        skip_info_cache = {}
        with SessionLocal() as db:
            from app.models import StockKline
            from sqlalchemy import func
            # 批量查询所有股票的最小/最大日期和记录数
            results = db.query(
                StockKline.stock_code,
                func.min(StockKline.trade_date).label('min_date'),
                func.max(StockKline.trade_date).label('max_date'),
                func.count(StockKline.id).label('count')
            ).group_by(StockKline.stock_code).all()
            
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            for stock_code, min_date, max_date, count in results:
                if count == 0:
                    skip_info_cache[stock_code] = (False, "no data")
                elif min_date <= end and max_date >= start:
                    skip_info_cache[stock_code] = (True, f"data exists ({min_date} to {max_date}, {count} records)")
                else:
                    skip_info_cache[stock_code] = (False, f"partial data ({min_date} to {max_date}, {count} records)")
        print(f"[INFO] Cached skip info for {len(skip_info_cache)} stocks")
        
        # 使用线程池并发处理
        from app.services import sync_service
        max_workers = 100
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_stock = {
                executor.submit(process_single_stock, stock, start_date, end_date, skipped_codes, existing_dates_cache, skip_info_cache, skip_check, only_skip_list): stock 
                for stock in filtered_stocks
            }
            
            # 批量保存数据（每10个成功结果保存一次）
            batch_save_size = 10
            batch_results = []
            
            # 处理完成的任务
            for future in as_completed(future_to_stock):
                if sync_status["cancelled"]:
                    print("\n[WARN] Sync cancelled by user")
                    # 取消所有未完成的任务
                    for f in future_to_stock:
                        f.cancel()
                    break
                
                stock = future_to_stock[future]
                stock_code = stock.code
                stock_name = stock.name
                
                try:
                    result = future.result()
                    
                    with lock:
                        count += 1
                        
                        if result["status"] == "success":
                            batch_results.append((stock_code, result["kline_data"]))
                            success_count += 1
                            print(f"[OK] [{count}/{total}] {stock_code} {stock_name} fetched {len(result['kline_data'])} records")
                            
                            # 批量保存
                            if len(batch_results) >= batch_save_size:
                                with SessionLocal() as db:
                                    for code, data in batch_results:
                                        sync_service.save_kline_data(db, code, data)
                                print(f"[INFO] Batch saved {len(batch_results)} stocks")
                                batch_results.clear()
                            
                        elif result["status"] == "skipped":
                            skipped_count += 1
                            print(f"[SKIP] [{count}/{total}] {stock_code} {stock_name} - {result['reason']}")
                            
                        elif result["status"] == "no_data":
                            no_data_stocks.append({"code": stock_code, "name": stock_name})
                            print(f"[WARN] [{count}/{total}] {stock_code} {stock_name} no data available")
                            
                        elif result["status"] == "failed":
                            failed_stocks.append({"code": stock_code, "name": stock_name})
                            print(f"[ERROR] [{count}/{total}] Failed to sync {stock_code}: {result['reason']}")
                        
                        # 更新进度
                        sync_status["progress"] = 20 + int((count / total) * 70)
                        sync_status["success_count"] = success_count
                        sync_status["failed_count"] = len(failed_stocks)
                        sync_status["skipped_count"] = skipped_count
                        sync_status["no_data_count"] = len(no_data_stocks)
                        sync_status["failed_stocks"] = failed_stocks
                        sync_status["no_data_stocks"] = no_data_stocks
                    
                except Exception as e:
                    with lock:
                        count += 1
                        failed_stocks.append({"code": stock_code, "name": stock_name})
                        print(f"[ERROR] [{count}/{total}] Failed to process {stock_code}: {e}")
                        sync_status["failed_count"] = len(failed_stocks)
                        sync_status["failed_stocks"] = failed_stocks
            
            # 保存剩余的批量结果
            if batch_results:
                with SessionLocal() as db:
                    for code, data in batch_results:
                        sync_service.save_kline_data(db, code, data)
                print(f"[INFO] Final batch saved {len(batch_results)} stocks")
        
        print("\n[STEP 3/3] Saving sync record...")
        sync_service.create_sync_record(end_date, total, success_count, skipped_count, len(failed_stocks), len(no_data_stocks), failed_stocks, no_data_stocks)
        
        print("=" * 50)
        print("[DONE] Sync completed!")
        print(f"  Total: {total}")
        print(f"  Success: {success_count}")
        print(f"  Skipped: {skipped_count}")
        print(f"  Failed: {len(failed_stocks)}")
        print(f"  No data: {len(no_data_stocks)}")
        if failed_stocks:
            print(f"\n  Failed stocks:")
            for s in failed_stocks:
                print(f"    - {s['code']} {s['name']}")
        if no_data_stocks:
            print(f"\n  No data stocks:")
            for s in no_data_stocks:
                print(f"    - {s['code']} {s['name']}")
        print("=" * 50)
        
    except Exception as e:
        if sync_status["cancelled"]:
            print("\n[WARN] Sync task cancelled")
            # 取消时也保存同步记录，记录当时的进度
            from app.services import sync_service
            sync_service.create_sync_record(
                end_date, total, success_count, skipped_count,
                len(failed_stocks), len(no_data_stocks),
                failed_stocks, no_data_stocks
            )
        else:
            print(f"[FATAL ERROR] Sync failed: {e}")
            import traceback
            traceback.print_exc()
    finally:
        sync_status["is_syncing"] = False


def cancel_sync():
    global sync_status
    if sync_status["is_syncing"]:
        sync_status["cancelled"] = True
        print("\n[INFO] Cancelling sync task...")


# 实时同步进度接口（轮询用）
@router.get("/progress")
async def get_sync_progress():
    return success(data={
        "is_syncing": sync_status["is_syncing"],
        "progress": sync_status["progress"],
        "success_count": sync_status.get("success_count", 0),
        "failed_count": sync_status.get("failed_count", 0),
        "skipped_count": sync_status.get("skipped_count", 0),
        "no_data_count": sync_status.get("no_data_count", 0),
        "failed_stocks": sync_status.get("failed_stocks", []),
        "no_data_stocks": sync_status.get("no_data_stocks", []),
    })


# 历史同步数据接口（查一次就行）
@router.get("/history")
async def get_sync_history(db: Session = Depends(get_db)):
    db_status = sync_service.get_sync_status()
    total_stocks_with_kline = stock_service.get_total_stocks_with_kline(db)
    return success(data={
        **db_status,
        "total_stocks_with_kline": total_stocks_with_kline,
    })


@router.post("/start")
async def start_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks
):
    if sync_status["is_syncing"]:
        return error(code=1, msg="已有同步任务在进行中")
    
    if not request.start_date or not request.end_date:
        return error(code=1, msg="起始时间和结束时间不能为空")
    
    background_tasks.add_task(run_sync_task, request.start_date, request.end_date, True)
    return success(msg="同步任务已启动")


@router.post("/start-recent-days")
async def start_sync_recent_days(
    background_tasks: BackgroundTasks
):
    """同步近10天数据，跳过排除列表，有则更新无则插入"""
    if sync_status["is_syncing"]:
        return error(code=1, msg="已有同步任务在进行中")
    
    # 计算近10天的日期范围
    today = datetime.now().date()
    # 找到最近10个交易日（考虑到周末和节假日，往前推15天）
    end_date = today
    start_date = today - timedelta(days=15)
    
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # skip_check=True 表示检查跳过列表，但跳过 should_skip_stock 检查（只检查排除列表）
    background_tasks.add_task(run_sync_task, start_date_str, end_date_str, True, True)
    return success(msg=f"近10天同步任务已启动（{start_date_str} 到 {end_date_str}）")


@router.post("/cancel")
async def cancel_sync_task():
    if not sync_status["is_syncing"]:
        return error(code=1, msg="没有同步任务在进行")
    
    cancel_sync()
    return success(msg="已发送取消请求")


@router.get("/skipped-stocks")
async def get_skipped_stocks():
    from app.utils.skipped_stocks import load_skipped_stocks
    skipped = load_skipped_stocks()
    return success(data={
        "count": len(skipped),
        "stocks": [{"code": code, "name": name} for code, name in skipped.items()],
    })


class AddSkippedStocksRequest(BaseModel):
    stocks: list


@router.post("/skipped-stocks/add")
async def add_skipped_stocks_api(request: AddSkippedStocksRequest):
    from app.utils.skipped_stocks import add_skipped_stocks
    stock_list = [(s["code"], s["name"]) for s in request.stocks]
    add_skipped_stocks(stock_list)
    return success(msg=f"已添加 {len(stock_list)} 个股票到跳过列表")


class RemoveSkippedStockRequest(BaseModel):
    code: str


@router.post("/skipped-stocks/remove")
async def remove_skipped_stock_api(request: RemoveSkippedStockRequest):
    from app.utils.skipped_stocks import remove_skipped_stock
    success_flag = remove_skipped_stock(request.code)
    if success_flag:
        return success(msg=f"已从跳过列表移除股票 {request.code}")
    else:
        return error(code=1, msg=f"股票 {request.code} 不在跳过列表中")
