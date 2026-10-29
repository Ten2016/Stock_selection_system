from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import date

from app.models.stock import StockBasic
from app.models.stock_kline import StockKline
from app.utils.db_helpers import apply_pagination, safe_like


SORT_FIELD_MAP = {
    'total_cap': StockBasic.total_cap,
    'pe_ratio': StockBasic.pe_ratio,
    'pb_ratio': StockBasic.pb_ratio,
    'ytd_change_pct': StockBasic.ytd_change_pct,
}


def get_stock_list(db: Session, skip: int = 0, limit: int = 50, min_market_cap: Optional[float] = None, search: Optional[str] = None, sort_by: Optional[str] = None, sort_order: str = "desc"):
    query = db.query(StockBasic).filter(StockBasic.is_active.is_(True))
    if min_market_cap is not None:
        query = query.filter(StockBasic.total_cap >= min_market_cap)
    if search:
        keyword = f"%{safe_like(search)}%"
        query = query.filter(or_(StockBasic.code.like(keyword, escape='\\'), StockBasic.name.like(keyword, escape='\\')))
    order_field = SORT_FIELD_MAP.get(sort_by, StockBasic.total_cap)
    query = query.order_by(order_field.asc() if sort_order == 'asc' else order_field.desc())
    total = query.count()
    stocks = apply_pagination(query, skip, limit).all()
    return stocks, total


def get_stock_by_code(db: Session, code: str):
    return db.query(StockBasic).filter(StockBasic.code == code).first()


def get_kline_data(db: Session, stock_code: str, start_date: Optional[date] = None, end_date: Optional[date] = None):
    query = db.query(StockKline).filter(StockKline.stock_code == stock_code)
    if start_date is not None:
        query = query.filter(StockKline.trade_date >= start_date)
    if end_date is not None:
        query = query.filter(StockKline.trade_date <= end_date)
    return query.order_by(StockKline.trade_date).all()


def get_kline_date_ranges(db: Session, stock_codes: list):
    """批量获取多只股票的 K 线日期区间，返回 {code: {...}}。列表页用，避免逐行查询。"""
    if not stock_codes:
        return {}
    rows = db.query(
        StockKline.stock_code,
        func.min(StockKline.trade_date).label('min_date'),
        func.max(StockKline.trade_date).label('max_date'),
        func.count(StockKline.id).label('count'),
    ).filter(StockKline.stock_code.in_(stock_codes)).group_by(StockKline.stock_code).all()
    return {
        row.stock_code: {
            'min_date': str(row.min_date) if row.min_date else None,
            'max_date': str(row.max_date) if row.max_date else None,
            'count': row.count,
        }
        for row in rows if row.count > 0
    }


def clear_stock_kline_data(db: Session, stock_code: str):
    deleted = db.query(StockKline).filter(StockKline.stock_code == stock_code).delete(synchronize_session=False)
    db.commit()
    return deleted


def get_total_stocks_with_kline(db: Session):
    return db.query(StockKline.stock_code).distinct().count()


def clear_all_stock_data(db: Session):
    deleted_kline = db.query(StockKline).delete(synchronize_session=False)
    deleted_basic = db.query(StockBasic).delete(synchronize_session=False)
    db.commit()
    return deleted_kline, deleted_basic
