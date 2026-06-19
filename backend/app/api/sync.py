import queue
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.utils.database import get_db
from app.utils.response import success, error
from app.utils.sync_state import sync_status, begin_sync, end_sync, request_cancel, update_counts, is_cancelled
from app.services import sync_service, stock_service
from datetime import datetime, timedelta

router = APIRouter()

# 拉取与入库流水线参数
FETCH_WORKERS = 4
SAVE_QUEUE_MAXSIZE = 30
BATCH_SAVE_SIZE = 40


class SyncRequest(BaseModel):
    start_date: str
    end_date: str


def _load_history_cache(db, stock_codes, history_start, sync_start):
    """仅预加载待同步股票的历史 close（指标计算上下文）。"""
    from app.models.stock_kline import StockKline

    if not stock_codes:
        return {}

    history_klines = db.query(StockKline).filter(
        StockKline.stock_code.in_(stock_codes),
        StockKline.trade_date >= history_start,
        StockKline.trade_date < sync_start,
    ).order_by(StockKline.stock_code.asc(), StockKline.trade_date.asc()).all()

    cache = {}
    for k in history_klines:
        if k.stock_code not in cache:
            cache[k.stock_code] = []
        cache[k.stock_code].append({'trade_date': k.trade_date, 'close': float(k.close)})
    return cache


def _process_single_stock(stock, start_date, end_date, skipped_codes, history_cache, skip_check=True):
    stock_code = stock.code
    stock_name = stock.name
    result = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "status": "pending",
        "reason": None,
        "kline_data": None,
    }

    try:
        if skip_check:
            from app.utils.skipped_stocks import is_skipped
            if is_skipped(stock_code, cached_codes=skipped_codes):
                result["status"] = "skipped"
                result["reason"] = "在跳过列表中"
                return result

        stock_history = history_cache.get(stock_code, [])
        kline_data = sync_service.fetch_one_stock_history(
            stock_code, start_date, end_date, stock_history
        )

        if len(kline_data) > 0:
            result["status"] = "success"
            result["kline_data"] = kline_data
        else:
            result["status"] = "no_data"
            result["reason"] = "no data available"

    except Exception as e:
        result["status"] = "failed"
        result["reason"] = str(e)
        import traceback
        traceback.print_exc()

    return result


def _run_save_worker(save_queue: queue.Queue, batch_save_size: int):
    """后台入库线程：攒批 upsert，单次事务提交。"""
    batch = []
    while True:
        try:
            item = save_queue.get(timeout=1.0)
        except queue.Empty:
            if batch:
                _flush_save_batch(batch)
                batch = []
            if is_cancelled() and save_queue.empty():
                break
            continue

        if item is None:
            save_queue.task_done()
            break

        batch.append(item)
        save_queue.task_done()

        if len(batch) >= batch_save_size:
            _flush_save_batch(batch)
            batch = []

    if batch:
        _flush_save_batch(batch)


def _flush_save_batch(batch):
    t0 = time.time()
    result = sync_service.save_kline_batch(batch)
    elapsed = time.time() - t0
    print(
        f"[INFO] Batch upserted {result['stock_count']} stocks "
        f"({result['row_count']} rows) in {elapsed:.2f}s"
    )


def run_sync_task(start_date: str, end_date: str, skip_check: bool = True, history_cache: dict = None):
    count = 0
    success_count = 0
    failed_stocks = []
    no_data_stocks = []
    skipped_count = 0
    total = 0
    lock = threading.Lock()

    save_queue = queue.Queue(maxsize=SAVE_QUEUE_MAXSIZE)
    saver_thread = threading.Thread(
        target=_run_save_worker,
        args=(save_queue, BATCH_SAVE_SIZE),
        daemon=True,
    )

    try:
        begin_sync()

        print("=" * 50)
        print("[START] Starting sync task")
        print(f"[INFO] Date range: {start_date} to {end_date}")
        print(f"[INFO] Fetch workers: {FETCH_WORKERS}, rate limit: {sync_service.KLINE_API_RATE_PER_SECOND}/s")
        print(f"[INFO] Save queue max: {SAVE_QUEUE_MAXSIZE}, batch size: {BATCH_SAVE_SIZE}")
        print(f"[INFO] Skip check: {'enabled' if skip_check else 'disabled'}")
        print("=" * 50)

        print("\n[STEP 1/3] Loading stocks from database...")
        from app.services.stock_service import get_stock_list
        from app.utils.database import SessionLocal

        with SessionLocal() as db_list:
            all_stocks, _ = get_stock_list(db_list, skip=0, limit=10000)

        MIN_MARKET_CAP = 100
        filtered_stocks = [
            s for s in all_stocks
            if s.code.startswith(('0', '3', '6')) and s.total_cap and s.total_cap >= MIN_MARKET_CAP
        ]
        skipped_small_cap = len([
            s for s in all_stocks
            if s.code.startswith(('0', '3', '6')) and (not s.total_cap or s.total_cap < MIN_MARKET_CAP)
        ])
        filtered_stocks.sort(key=lambda x: x.total_cap if x.total_cap else 0, reverse=True)

        total = len(filtered_stocks)
        print(f"[INFO] Loaded {total} stocks (filtered from {len(all_stocks)})")
        print(f"[INFO] Skipped {skipped_small_cap} stocks with market cap < {MIN_MARKET_CAP}亿")

        sync_status["progress"] = 20

        from app.utils.skipped_stocks import load_skipped_codes
        skipped_codes = load_skipped_codes()
        print(f"[INFO] Loaded {len(skipped_codes)} stocks from skip list")

        print("\n[STEP 1.5/3] Pre-loading historical data for indicator calculation...")
        start_date_clean = start_date.replace('-', '')
        sync_start_date_obj = datetime.strptime(start_date_clean, "%Y%m%d").date()
        history_start_date_obj = sync_start_date_obj - timedelta(days=120)
        filtered_codes = [s.code for s in filtered_stocks]

        with SessionLocal() as db_cache:
            local_history_cache = _load_history_cache(
                db_cache, filtered_codes, history_start_date_obj, sync_start_date_obj
            )

        print(f"[INFO] Pre-loaded history for {len(local_history_cache)} stocks", flush=True)

        print("\n[STEP 2/3] Syncing K-line data (pipeline: fetch + async save)...", flush=True)
        saver_thread.start()

        def fetch_and_enqueue(stock):
            result = _process_single_stock(
                stock, start_date, end_date, skipped_codes, local_history_cache, skip_check
            )
            if result["status"] == "success":
                # 队列满时阻塞，自然降低 API 请求速率
                save_queue.put((result["stock_code"], result["kline_data"]))
            return result

        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as executor:
            future_to_stock = {
                executor.submit(fetch_and_enqueue, stock): stock
                for stock in filtered_stocks
            }

            for future in as_completed(future_to_stock):
                if is_cancelled():
                    print("\n[WARN] Sync cancelled by user")
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
                            success_count += 1
                            print(
                                f"[OK] [{count}/{total}] {stock_code} {stock_name} "
                                f"fetched {len(result['kline_data'])} records"
                            )
                        elif result["status"] == "skipped":
                            skipped_count += 1
                            print(f"[SKIP] [{count}/{total}] {stock_code} {stock_name} - {result['reason']}")
                        elif result["status"] == "no_data":
                            no_data_stocks.append({"code": stock_code, "name": stock_name})
                            print(f"[WARN] [{count}/{total}] {stock_code} {stock_name} no data available")
                        elif result["status"] == "failed":
                            failed_stocks.append({"code": stock_code, "name": stock_name})
                            print(f"[ERROR] [{count}/{total}] Failed to sync {stock_code}: {result['reason']}")

                        progress = 20 + int((count / total) * 70) if total else 100
                        update_counts(success_count, skipped_count, failed_stocks, no_data_stocks, progress)

                except Exception as e:
                    with lock:
                        count += 1
                        failed_stocks.append({"code": stock_code, "name": stock_name})
                        print(f"[ERROR] [{count}/{total}] Failed to process {stock_code}: {e}")
                        progress = 20 + int((count / total) * 70) if total else 100
                        update_counts(success_count, skipped_count, failed_stocks, no_data_stocks, progress)

        save_queue.put(None)
        saver_thread.join(timeout=300)

        print("\n[STEP 3/3] Saving sync record...")
        sync_service.create_sync_record(
            end_date, total, success_count, skipped_count,
            len(failed_stocks), len(no_data_stocks), failed_stocks, no_data_stocks,
        )

        print("=" * 50)
        print("[DONE] Sync completed!")
        print(f"  Total: {total}")
        print(f"  Success: {success_count}")
        print(f"  Skipped: {skipped_count}")
        print(f"  Failed: {len(failed_stocks)}")
        print(f"  No data: {len(no_data_stocks)}")
        print("=" * 50)

    except Exception as e:
        if is_cancelled():
            print("\n[WARN] Sync task cancelled")
            sync_service.create_sync_record(
                end_date, total, success_count, skipped_count,
                len(failed_stocks), len(no_data_stocks), failed_stocks, no_data_stocks,
            )
        else:
            print(f"[FATAL ERROR] Sync failed: {e}")
            import traceback
            traceback.print_exc()
    finally:
        if saver_thread.is_alive():
            save_queue.put(None)
            saver_thread.join(timeout=60)
        end_sync()


def cancel_sync():
    request_cancel()
    print("\n[INFO] Cancelling sync task...")


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

    today = datetime.now().date()
    end_date = today
    start_date = today - timedelta(days=15)

    start_date_str = start_date.strftime('%Y%m%d')
    end_date_str = end_date.strftime('%Y%m%d')

    background_tasks.add_task(run_sync_task, start_date_str, end_date_str, True)
    return success(msg=f"近10天同步任务已启动（{start_date_str} 到 {end_date_str}）")


@router.post("/sync-basic-info")
async def sync_basic_info(
    background_tasks: BackgroundTasks
):
    """只同步股票基本信息（市值、市盈率等），不同步K线"""
    if sync_status["is_syncing"]:
        return error(code=1, msg="已有同步任务在进行中")

    background_tasks.add_task(sync_service.run_basic_info_sync)
    return success(msg="基本信息同步任务已启动")


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


class SkippedStockItem(BaseModel):
    code: str
    name: str


class AddSkippedStocksRequest(BaseModel):
    stocks: list[SkippedStockItem] = Field(default_factory=list)


@router.post("/skipped-stocks/add")
async def add_skipped_stocks_api(request: AddSkippedStocksRequest):
    from app.utils.skipped_stocks import add_skipped_stocks
    stock_list = [(s.code, s.name) for s in request.stocks]
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
