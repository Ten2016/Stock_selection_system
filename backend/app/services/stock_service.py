from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from app.models.stock import StockBasic
from app.models.stock_kline import StockKline


def get_stock_list(db: Session, skip: int = 0, limit: int = 50, min_market_cap: Optional[float] = None, search: Optional[str] = None, sort_by: Optional[str] = None, sort_order: str = "desc"):
    query = db.query(StockBasic).filter(StockBasic.is_active == True)
    
    if min_market_cap is not None:
        query = query.filter(StockBasic.total_cap >= min_market_cap)
    
    if search:
        query = query.filter(
            (StockBasic.code.like(f'%{search}%')) | (StockBasic.name.like(f'%{search}%'))
        )
    
    # 排序字段映射
    sort_field_map = {
        'total_cap': StockBasic.total_cap,
        'pe_ratio': StockBasic.pe_ratio,
        'pb_ratio': StockBasic.pb_ratio,
        'ytd_change_pct': StockBasic.ytd_change_pct,
    }
    
    # 默认排序：按总市值降序
    order_field = sort_field_map.get(sort_by, StockBasic.total_cap)
    if sort_order == 'asc':
        query = query.order_by(order_field.asc())
    else:
        query = query.order_by(order_field.desc())
    
    total = query.count()
    stocks = query.offset(skip).limit(limit).all()
    
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


def get_stock_kline_date_range(db: Session, stock_code: str):
    result = db.query(
        func.min(StockKline.trade_date).label('min_date'),
        func.max(StockKline.trade_date).label('max_date'),
        func.count(StockKline.id).label('count')
    ).filter(StockKline.stock_code == stock_code).first()
    
    if result and result.count > 0:
        return {
            'min_date': str(result.min_date) if result.min_date else None,
            'max_date': str(result.max_date) if result.max_date else None,
            'count': result.count
        }
    return None


def clear_stock_kline_data(db: Session, stock_code: str):
    deleted = db.query(StockKline).filter(StockKline.stock_code == stock_code).delete()
    db.commit()
    return deleted


def get_total_stocks_with_kline(db: Session):
    return db.query(StockKline.stock_code).distinct().count()


def clear_all_kline_data(db: Session):
    deleted = db.query(StockKline).delete()
    db.commit()
    return deleted


def clear_all_stock_basic(db: Session):
    deleted = db.query(StockBasic).delete()
    db.commit()
    return deleted
