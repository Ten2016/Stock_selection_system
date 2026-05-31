from sqlalchemy import Column, Integer, String, Date, TIMESTAMP, DECIMAL, JSON, Index
from sqlalchemy.sql import func

from app.utils.database import Base


class StockKline(Base):
    __tablename__ = "stock_kline"
    __table_args__ = (
        Index('idx_stock_code_trade_date', 'stock_code', 'trade_date'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, index=True)
    trade_date = Column(Date, nullable=False)
    open = Column(DECIMAL(10, 2), nullable=False)
    high = Column(DECIMAL(10, 2), nullable=False)
    low = Column(DECIMAL(10, 2), nullable=False)
    close = Column(DECIMAL(10, 2), nullable=False)
    volume = Column(DECIMAL(20, 2))
    amount = Column(DECIMAL(20, 2))
    amplitude = Column(DECIMAL(10, 2))
    change_pct = Column(DECIMAL(10, 2))
    turnover_rate = Column(DECIMAL(10, 2))
    ma5 = Column(DECIMAL(10, 2))
    ma10 = Column(DECIMAL(10, 2))
    ma20 = Column(DECIMAL(10, 2))
    ma30 = Column(DECIMAL(10, 2))
    ma60 = Column(DECIMAL(10, 2))
    ma120 = Column(DECIMAL(10, 2))
    boll_upper = Column(DECIMAL(10, 2))
    boll_mid = Column(DECIMAL(10, 2))
    boll_lower = Column(DECIMAL(10, 2))
    dividend_info = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

    def to_dict(self):
        return {
            "stock_code": self.stock_code,
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "amount": self.amount,
            "amplitude": self.amplitude,
            "change_pct": self.change_pct,
            "turnover_rate": self.turnover_rate,
            "ma5": self.ma5,
            "ma10": self.ma10,
            "ma20": self.ma20,
            "ma30": self.ma30,
            "ma60": self.ma60,
            "ma120": self.ma120,
            "boll_upper": self.boll_upper,
            "boll_mid": self.boll_mid,
            "boll_lower": self.boll_lower,
            "dividend_info": self.dividend_info,
        }
