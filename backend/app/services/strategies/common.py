from typing import List
from sqlalchemy.orm import Session

from app.models.stock_kline import StockKline


def get_sorted_klines(stock_code: str, db: Session, max_days: int = 200) -> List[StockKline]:
    data = db.query(StockKline).filter(
        StockKline.stock_code == stock_code
    ).order_by(StockKline.trade_date.desc()).limit(max_days).all()
    return sorted(data, key=lambda x: x.trade_date)
