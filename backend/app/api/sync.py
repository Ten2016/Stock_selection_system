import time
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


def run_sync_task(start_date: str, end_date: str):
    global sync_status
    # 在函数最开始初始化所有变量，避免作用域问题
    count = 0
    success_count = 0
    failed_stocks = []
    no_data_stocks = []
    skipped_count = 0
    total = 0
    db = None
    try:
        sync_status["is_syncing"] = True
        sync_status["progress"] = 0
        sync_status["cancelled"] = False
        
        print("=" * 50)
        print("[START] Starting sync task")
        print(f"[INFO] Date range: {start_date} to {end_date}")
        print("[INFO] Press Ctrl+C to cancel sync")
        print("=" * 50)
        
        print("\n[STEP 1/3] Loading stocks from database...")
        from app.services.stock_service import get_stock_list
        from app.utils.database import SessionLocal
        with SessionLocal() as db_list:
            all_stocks, _ = get_stock_list(db_list, skip=0, limit=10000)
        
        filtered_stocks = [s for s in all_stocks if s.code.startswith(('0', '3', '6'))]
        total = len(filtered_stocks)
        print(f"[INFO] Loaded {total} stocks (filtered from {len(all_stocks)})")
        
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
        
        db = SessionLocal()
        try:
            # 加载跳过的股票列表（只读一次）
            from app.utils.skipped_stocks import load_skipped_codes, is_skipped
            skipped_codes = load_skipped_codes()
            print(f"[INFO] Loaded {len(skipped_codes)} stocks from skip list")
            
            for stock in filtered_stocks:
                if sync_status["cancelled"]:
                    print("\n[WARN] Sync cancelled by user")
                    break
                
                try:
                    stock_code = stock.code
                    stock_name = stock.name
                    
                    # 检查是否在跳过列表中（使用缓存集合，不再每次读文件）
                    if is_skipped(stock_code, cached_codes=skipped_codes):
                        print(f"[SKIP] [{count+1}/{total}] {stock_code} {stock_name} - 在跳过列表中")
                        skipped_count += 1
                        count += 1
                        sync_status["progress"] = 20 + int((count / total) * 70)
                        sync_status["skipped_count"] = skipped_count
                        continue
                    
                    should_skip, reason = sync_service.should_skip_stock(db, stock_code, start_date, end_date)
                    if should_skip:
                        print(f"[SKIP] [{count+1}/{total}] {stock_code} {stock_name} - {reason}")
                        skipped_count += 1
                        count += 1
                        sync_status["progress"] = 20 + int((count / total) * 70)
                        sync_status["skipped_count"] = skipped_count
                        continue
                    
                    print(f"[WORK] [{count+1}/{total}] Syncing {stock_code} {stock_name}...")
                    existing_dates = sync_service.get_existing_dates(db, stock_code)
                    kline_data = sync_service.fetch_one_stock_history_with_db(stock_code, start_date, end_date, existing_dates)
                    
                    if len(kline_data) > 0:
                        sync_service.save_kline_data(db, stock_code, kline_data)
                        success_count += 1
                        print(f"[OK] [{count+1}/{total}] {stock_code} {stock_name} saved {len(kline_data)} records")
                    else:
                        no_data_stocks.append({"code": stock_code, "name": stock_name})
                        print(f"[WARN] [{count+1}/{total}] {stock_code} {stock_name} no data available")
                    
                    count += 1
                    sync_status["progress"] = 20 + int((count / total) * 70)
                    sync_status["success_count"] = success_count
                    sync_status["failed_count"] = len(failed_stocks)
                    sync_status["no_data_count"] = len(no_data_stocks)
                    sync_status["failed_stocks"] = failed_stocks
                    sync_status["no_data_stocks"] = no_data_stocks
                    
                    time.sleep(0.05)
                except Exception as e:
                    failed_stocks.append({"code": stock_code, "name": stock_name})
                    count += 1
                    print(f"[ERROR] [{count}/{total}] Failed to sync {stock_code}: {e}")
                    sync_status["failed_count"] = len(failed_stocks)
                    sync_status["failed_stocks"] = failed_stocks
        finally:
            if db:
                db.close()
        
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
    
    background_tasks.add_task(run_sync_task, request.start_date, request.end_date)
    return success(msg="同步任务已启动")


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
