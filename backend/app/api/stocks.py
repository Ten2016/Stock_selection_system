from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from app.utils.database import get_db
from app.utils.response import success, error
from app.services import stock_service

router = APIRouter()


@router.get("")
async def get_stocks(
    skip: int = 0,
    limit: int = 50,
    min_market_cap: Optional[float] = Query(None, description="Minimum market capitalization in hundred million yuan"),
    search: Optional[str] = Query(None, description="Search by stock code or name"),
    sort_by: Optional[str] = Query(None, description="Sort field: total_cap, pe_ratio, pb_ratio, ytd_change_pct"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db)
):
    stocks, total = stock_service.get_stock_list(db, skip=skip, limit=limit, min_market_cap=min_market_cap, search=search, sort_by=sort_by, sort_order=sort_order)
    
    result = []
    for stock in stocks:
        stock_dict = stock.to_dict()
        
        date_range = stock_service.get_stock_kline_date_range(db, stock.code)
        if date_range:
            stock_dict['kline_date_range'] = date_range
        else:
            stock_dict['kline_date_range'] = None
        
        result.append(stock_dict)
    
    return success(data={
        "list": result,
        "total": total,
        "skip": skip,
        "limit": limit,
    })


@router.get("/{code}")
async def get_stock(code: str, db: Session = Depends(get_db)):
    stock = stock_service.get_stock_by_code(db, code)
    if not stock:
        return error(code=1, msg="股票不存在")
    return success(data=stock.to_dict())


@router.get("/{code}/kline")
async def get_kline(
    code: str,
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    klines = stock_service.get_kline_data(db, code, start_date=start_date, end_date=end_date)
    result = [kline.to_dict() for kline in klines]
    return success(data={
        "stock_code": code,
        "klines": result,
    })


@router.delete("/{code}/kline")
async def clear_stock_kline(code: str, db: Session = Depends(get_db)):
    deleted = stock_service.clear_stock_kline_data(db, code)
    return success(msg=f"已删除股票 {code} 的 {deleted} 条K线数据", data={"deleted": deleted})


@router.delete("/all")
async def clear_all_stock_data(db: Session = Depends(get_db)):
    deleted_kline = stock_service.clear_all_kline_data(db)
    deleted_basic = stock_service.clear_all_stock_basic(db)
    return success(msg="已清空所有数据", data={
        "deleted_kline": deleted_kline,
        "deleted_basic": deleted_basic,
    })
