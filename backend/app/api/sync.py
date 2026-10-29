import queue
import time
import threading
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.utils.database import get_db, SessionLocal
from app.utils.response import success, error
from app.utils.sync_state import sync_status, begin_sync, end_sync, request_cancel, update_counts, is_cancelled
from app.services import sync_service, stock_service
from datetime import datetime, timedelta

router = APIRouter()

# 拉取与入库流水线参数
FETCH_WORKERS = 4
SAVE_QUEUE_MAXSIZE = 8
BATCH_SAVE_SIZE = 8

# 同步区间向前扩展的天数：覆盖节假日/周末，保证与库中已有数据存在重叠日，
# 复权漂移检测依赖这段重叠来判断历史价格是否已失效。
SYNC_BUFFER_DAYS = 10

# 新股票额外拉取历史，供 MA60 / MACD 初始化，并保存作为后续计算起点。
INITIAL_CONTEXT_DAYS = 365


class SyncRequest(BaseModel):
    start_date: str
    end_date: str


def _load_sync_context(db, stock_code, fetch_start, fetch_end):
    """按股票读取完整收盘价序列，避免截断 EMA，也限制并发内存占用。"""
    from app.models.stock_kline import StockKline

    rows = db.query(StockKline.trade_date, StockKline.close).filter(
        StockKline.stock_code == stock_code
    ).order_by(StockKline.trade_date.asc()).all()
    earliest = rows[0].trade_date if rows else None
    latest = rows[-1].trade_date if rows else None
    if latest:
        fetch_start = min(fetch_start, latest)
        fetch_end = max(fetch_end, latest)
    else:
        fetch_start -= timedelta(days=INITIAL_CONTEXT_DAYS)
    return {
        'earliest': earliest,
        'fetch_start': fetch_start,
        'fetch_end': fetch_end,
        'history': [{'trade_date': day, 'close': float(close)}
                    for day, close in rows if day < fetch_start],
        'overlap': {day: float(close) for day, close in rows if day >= fetch_start},
        'stored_dates': {day for day, _ in rows},
    }


def _process_single_stock(stock, start_date, end_date, skipped_codes, skip_check=True):
    stock_code = stock.code
    result = {
        'stock_code': stock_code, 'stock_name': stock.name,
        'status': 'pending', 'reason': None, 'kline_data': None, 'full_resync': False,
    }
    try:
        if is_cancelled():
            raise CancelledError()
        if skip_check:
            from app.utils.skipped_stocks import is_skipped
            if is_skipped(stock_code, cached_codes=skipped_codes):
                result.update(status='skipped', reason='在跳过列表中')
                return result

        start = datetime.strptime(start_date.replace('-', ''), '%Y%m%d').date()
        end = datetime.strptime(end_date.replace('-', ''), '%Y%m%d').date()
        with SessionLocal() as db:
            ctx = _load_sync_context(db, stock_code, start, end)
        fetch_start, fetch_end = ctx['fetch_start'], ctx['fetch_end']
        kline_data = sync_service.fetch_one_stock_history(
            stock_code, fetch_start.isoformat(), fetch_end.isoformat(), ctx['history']
        )
        if is_cancelled():
            raise CancelledError()
        if kline_data.empty:
            if ctx['overlap']:
                raise ValueError('上游未返回区间内已有的历史数据，未覆盖本地数据')
            result.update(status='no_data', reason='区间内无交易数据')
            return result

        resync_reason = _need_full_resync(kline_data, ctx, fetch_start.isoformat())
        if resync_reason:
            fetch_start = min(ctx['earliest'], fetch_start)
            print(f'[QFQ] {stock_code} 全量重拉：{resync_reason}', flush=True)
            kline_data = sync_service.fetch_one_stock_history(
                stock_code, fetch_start.isoformat(), fetch_end.isoformat()
            )
            result.update(full_resync=True, reason=resync_reason)
        if is_cancelled():
            raise CancelledError()
        if kline_data.empty:
            raise ValueError('全量重拉未返回数据，未覆盖本地数据')
        expected_dates = {day for day in ctx['stored_dates'] if fetch_start <= day <= fetch_end}
        missing_dates = expected_dates - set(kline_data['trade_date'])
        if missing_dates:
            raise ValueError(f'上游缺少 {len(missing_dates)} 个已存交易日（最早 {min(missing_dates)}），未覆盖本地数据')
        result.update(status='success', kline_data=kline_data)
    except CancelledError:
        result['status'] = 'cancelled'
    except Exception as exc:
        result.update(status='failed', reason=str(exc))
        import traceback
        traceback.print_exc()
    return result


def _need_full_resync(kline_data, ctx, fetch_start: str):
    """重叠价格变化或无法验证衔接时，整只股票统一复权口径。"""
    earliest = ctx.get('earliest')
    fetch_start_date = datetime.strptime(fetch_start.replace('-', ''), '%Y%m%d').date()
    if not earliest or earliest >= fetch_start_date:
        return None
    overlap = ctx.get('overlap') or {}
    if not set(kline_data['trade_date']).intersection(overlap):
        return '无共同交易日，无法确认复权口径一致'
    drift = sync_service.detect_qfq_drift(kline_data, overlap)
    if drift:
        return f'前复权价格变化（{drift}）'
    return None


def _run_save_worker(save_queue: queue.Queue, batch_save_size: int, save_state: dict):
    """后台入库线程：攒批 upsert，单次事务提交。"""
    batch = []
    try:
        while True:
            try:
                item = save_queue.get(timeout=1.0)
            except queue.Empty:
                if batch:
                    _flush_save_batch(batch, save_state)
                    batch = []
                continue

            save_queue.task_done()
            if item is None:
                break
            batch.append(item)
            if len(batch) >= batch_save_size:
                _flush_save_batch(batch, save_state)
                batch = []

        if batch:
            _flush_save_batch(batch, save_state)
    except Exception as exc:
        save_state['error'] = exc


def _flush_save_batch(batch, save_state):
    t0 = time.time()
    result = sync_service.save_kline_batch(batch)
    save_state['saved_codes'].update(code for code, _ in batch)
    elapsed = time.time() - t0
    print(
        f"[INFO] Batch upserted {result['stock_count']} stocks "
        f"({result['row_count']} rows) in {elapsed:.2f}s"
    )


def run_sync_task(start_date: str, end_date: str, skip_check: bool = True):
    count = 0
    resync_count = 0
    failed_stocks = []
    no_data_stocks = []
    skipped_count = 0
    total = 0
    lock = threading.Lock()

    save_state = {'saved_codes': set(), 'error': None}
    error_msg = None
    filtered_stocks = []
    skipped_codes = set()
    save_queue = queue.Queue(maxsize=SAVE_QUEUE_MAXSIZE)
    saver_thread = threading.Thread(
        target=_run_save_worker,
        args=(save_queue, BATCH_SAVE_SIZE, save_state),
        daemon=True,
    )

    try:
        requested_start = start_date.replace('-', '')
        end_date_clean = end_date.replace('-', '')

        # 仅向前扩展少量缓冲日，用于覆盖节假日并与库中数据形成重叠（复权漂移检测所需）。
        # 真正需要重拉历史的股票由 _need_full_resync 单独识别，不再无差别前推一年。
        requested_start_obj = datetime.strptime(requested_start, "%Y%m%d").date()
        fetch_start_obj = requested_start_obj - timedelta(days=SYNC_BUFFER_DAYS)
        start_date_clean = fetch_start_obj.strftime("%Y%m%d")

        print("=" * 50)
        print("[START] Starting sync task")
        print(f"[INFO] Requested range: {requested_start} to {end_date_clean}")
        print(f"[INFO] Fetch range (+{SYNC_BUFFER_DAYS}d buffer): {start_date_clean} to {end_date_clean}")
        print(f"[INFO] Fetch workers: {FETCH_WORKERS}, rate limit: {sync_service.KLINE_API_RATE_PER_SECOND}/s")
        print(f"[INFO] Save queue max: {SAVE_QUEUE_MAXSIZE}, batch size: {BATCH_SAVE_SIZE}")
        print(f"[INFO] Skip check: {'enabled' if skip_check else 'disabled'}")
        print("=" * 50)

        print("\n[STEP 1/3] Loading stocks from database...")
        from app.services.stock_service import get_stock_list

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

        print("\n[STEP 2/3] Syncing K-line data (pipeline: fetch + async save)...", flush=True)
        saver_thread.start()

        def fetch_and_enqueue(stock):
            if is_cancelled() or save_state['error'] is not None:
                return {'status': 'cancelled'}
            result = _process_single_stock(
                stock, start_date_clean, end_date_clean, skipped_codes, skip_check
            )
            if result["status"] == "success":
                while True:
                    if save_state['error'] is not None:
                        raise RuntimeError(f"K线写入失败：{save_state['error']}")
                    if is_cancelled():
                        result['status'] = 'cancelled'
                        break
                    try:
                        save_queue.put((result["stock_code"], result["kline_data"]), timeout=0.2)
                        break
                    except queue.Full:
                        continue
            result.pop('kline_data', None)
            return result

        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as executor:
            future_to_stock = {
                executor.submit(fetch_and_enqueue, stock): stock
                for stock in filtered_stocks
            }

            for future in as_completed(future_to_stock):
                if save_state['error'] is not None:
                    for f in future_to_stock:
                        f.cancel()
                    raise RuntimeError(f"K线写入失败：{save_state['error']}")
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
                            if result.get("full_resync"):
                                resync_count += 1
                            tag = " [FULL-RESYNC]" if result.get("full_resync") else ""
                            print(
                                f"[OK] [{count}/{total}] {stock_code} {stock_name} "
                                f"fetched{tag}"
                            )
                        elif result["status"] == "skipped":
                            skipped_count += 1
                            print(f"[SKIP] [{count}/{total}] {stock_code} {stock_name} - {result['reason']}")
                        elif result["status"] == "no_data":
                            no_data_stocks.append({"code": stock_code, "name": stock_name})
                            print(f"[WARN] [{count}/{total}] {stock_code} {stock_name} no data available")
                        elif result["status"] == "failed":
                            failed_stocks.append({"code": stock_code, "name": stock_name, "reason": result["reason"]})
                            print(f"[ERROR] [{count}/{total}] Failed to sync {stock_code}: {result['reason']}")

                        progress = 20 + int((count / total) * 70) if total else 100
                        update_counts(len(save_state['saved_codes']), skipped_count, failed_stocks, no_data_stocks, progress)

                except Exception as e:
                    with lock:
                        count += 1
                        failed_stocks.append({"code": stock_code, "name": stock_name})
                        print(f"[ERROR] [{count}/{total}] Failed to process {stock_code}: {e}")
                        progress = 20 + int((count / total) * 70) if total else 100
                        update_counts(len(save_state['saved_codes']), skipped_count, failed_stocks, no_data_stocks, progress)

    except Exception as exc:
        error_msg = str(exc)
        print(f"[FATAL ERROR] Sync failed: {exc}")
        import traceback
        traceback.print_exc()
    finally:
        # 生产者全部退出后才发送结束标记，取消时也要写完已入队的数据。
        while saver_thread.is_alive():
            try:
                save_queue.put(None, timeout=0.2)
                break
            except queue.Full:
                continue
        if saver_thread.ident is not None:
            saver_thread.join()
        if save_state['error'] is not None:
            error_msg = f"K线写入失败：{save_state['error']}"
        success_count = len(save_state['saved_codes'])
        if error_msg:
            failed_codes = {s['code'] for s in failed_stocks}
            no_data_codes = {s['code'] for s in no_data_stocks}
            for stock in filtered_stocks:
                if stock.code not in save_state['saved_codes'] | failed_codes | no_data_codes:
                    if skip_check and stock.code in skipped_codes:
                        continue
                    failed_stocks.append({'code': stock.code, 'name': stock.name})
        update_counts(success_count, skipped_count, failed_stocks, no_data_stocks, sync_status['progress'])
        status = 'failed' if error_msg else (
            'cancelled' if is_cancelled() else ('partial' if failed_stocks else 'success')
        )
        try:
            sync_service.create_sync_record(
                end_date, total, success_count, skipped_count,
                len(failed_stocks), len(no_data_stocks), failed_stocks, no_data_stocks,
                status=status, error_msg=error_msg,
            )
        except Exception as exc:
            error_msg = error_msg or f"保存同步记录失败：{exc}"
        finally:
            end_sync(error_msg)
        print(f"[DONE] Sync {sync_status['status']}: saved={success_count}, failed={len(failed_stocks)}, resynced={resync_count}")


def cancel_sync():
    request_cancel()
    print("\n[INFO] Cancelling sync task...")


@router.get("/progress")
async def get_sync_progress():
    return success(data={
        "is_syncing": sync_status["is_syncing"],
        "progress": sync_status["progress"],
        "status": sync_status["status"],
        "error_msg": sync_status["error_msg"],
        "success_count": sync_status.get("success_count", 0),
        "failed_count": sync_status.get("failed_count", 0),
        "skipped_count": sync_status.get("skipped_count", 0),
        "no_data_count": sync_status.get("no_data_count", 0),
        "failed_stocks": sync_status.get("failed_stocks", []),
        "no_data_stocks": sync_status.get("no_data_stocks", []),
    })


@router.get("/history")
def get_sync_history(db: Session = Depends(get_db)):
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
    try:
        start = datetime.strptime(request.start_date.replace('-', ''), '%Y%m%d').date()
        end = datetime.strptime(request.end_date.replace('-', ''), '%Y%m%d').date()
    except ValueError:
        return error(code=1, msg="日期格式应为 YYYY-MM-DD 或 YYYYMMDD")
    if start > end:
        return error(code=1, msg="起始日期不能晚于结束日期")
    end = min(end, sync_service.latest_completed_date())
    if start > end:
        return error(code=1, msg="所选区间尚无已收盘日线，请在收盘后同步")
    if not begin_sync():
        return error(code=1, msg="已有同步任务在进行中")

    background_tasks.add_task(run_sync_task, start.isoformat(), end.isoformat(), True)
    return success(msg=f"同步任务已启动（日线截至 {end.isoformat()}）")


class SyncRecentDaysRequest(BaseModel):
    days: int = Field(default=10, ge=1, le=365, description="同步最近N天")


@router.post("/start-recent-days")
async def start_sync_recent_days(
    request: SyncRecentDaysRequest,
    background_tasks: BackgroundTasks
):
    """同步近N天数据，跳过排除列表，有则更新无则插入"""
    if not begin_sync():
        return error(code=1, msg="已有同步任务在进行中")

    end_date = sync_service.latest_completed_date()
    start_date = end_date - timedelta(days=request.days - 1)

    start_date_str = start_date.strftime('%Y%m%d')
    end_date_str = end_date.strftime('%Y%m%d')

    background_tasks.add_task(run_sync_task, start_date_str, end_date_str, True)
    return success(msg=f"近{request.days}天同步任务已启动（{start_date_str} 到 {end_date_str}）")


@router.post("/sync-basic-info")
async def sync_basic_info(
    background_tasks: BackgroundTasks
):
    """只同步股票基本信息（市值、市盈率等），不同步K线"""
    if not begin_sync():
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


@router.post("/repair-indicators")
async def repair_indicators(
    background_tasks: BackgroundTasks
):
    """修复所有股票的K线指标数据"""
    if not begin_sync():
        return error(code=1, msg="已有同步任务在进行中")

    background_tasks.add_task(sync_service.run_repair_indicators)
    return success(msg="指标修复任务已启动")
