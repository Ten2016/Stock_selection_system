from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from app.utils.database import get_db
from app.utils.response import success, error
from app.services import stock_service
from app.utils.sync_state import sync_status

router = APIRouter()


@router.get("")
def get_stocks(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=10000),
    min_market_cap: Optional[float] = Query(None, ge=0, allow_inf_nan=False, description="Minimum market capitalization in hundred million yuan"),
    search: Optional[str] = Query(None, description="Search by stock code or name"),
    sort_by: Optional[str] = Query(None, description="Sort field: total_cap, pe_ratio, pb_ratio, ytd_change_pct"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db)
):
    stocks, total = stock_service.get_stock_list(db, skip=skip, limit=limit, min_market_cap=min_market_cap, search=search, sort_by=sort_by, sort_order=sort_order)

    date_ranges = stock_service.get_kline_date_ranges(db, [s.code for s in stocks])

    result = []
    for stock in stocks:
        stock_dict = stock.to_dict()
        stock_dict['kline_date_range'] = date_ranges.get(stock.code)
        result.append(stock_dict)

    return success(data={
        "list": result,
        "total": total,
        "skip": skip,
        "limit": limit,
    })


@router.get("/{code}")
def get_stock(code: str, db: Session = Depends(get_db)):
    stock = stock_service.get_stock_by_code(db, code)
    if not stock:
        return error(code=1, msg="股票不存在")
    return success(data=stock.to_dict())


@router.get("/{code}/kline")
def get_kline(
    code: str,
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    if start_date and end_date and start_date > end_date:
        return error(code=1, msg="起始日期不能晚于结束日期")
    klines = stock_service.get_kline_data(db, code, start_date=start_date, end_date=end_date)
    result = [kline.to_dict() for kline in klines]
    return success(data={
        "stock_code": code,
        "klines": result,
    })


@router.delete("/{code}/kline")
def clear_stock_kline(code: str, db: Session = Depends(get_db)):
    if sync_status['is_syncing']:
        return error(code=1, msg="同步或修复任务进行中，请结束后再清理数据")
    deleted = stock_service.clear_stock_kline_data(db, code)
    return success(msg=f"已删除股票 {code} 的 {deleted} 条K线数据", data={"deleted": deleted})


@router.delete("/all")
def clear_all_stock_data(db: Session = Depends(get_db)):
    if sync_status['is_syncing']:
        return error(code=1, msg="同步或修复任务进行中，请结束后再清理数据")
    deleted_kline, deleted_basic = stock_service.clear_all_stock_data(db)
    return success(msg="已清空所有数据", data={
        "deleted_kline": deleted_kline,
        "deleted_basic": deleted_basic,
    })
