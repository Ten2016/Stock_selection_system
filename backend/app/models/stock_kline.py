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
            "open": float(self.open) if self.open else None,
            "high": float(self.high) if self.high else None,
            "low": float(self.low) if self.low else None,
            "close": float(self.close) if self.close else None,
            "volume": float(self.volume) if self.volume else None,
            "amount": float(self.amount) if self.amount else None,
            "amplitude": float(self.amplitude) if self.amplitude else None,
            "change_pct": float(self.change_pct) if self.change_pct else None,
            "turnover_rate": float(self.turnover_rate) if self.turnover_rate else None,
            "ma5": float(self.ma5) if self.ma5 else None,
            "ma10": float(self.ma10) if self.ma10 else None,
            "ma20": float(self.ma20) if self.ma20 else None,
            "ma30": float(self.ma30) if self.ma30 else None,
            "ma60": float(self.ma60) if self.ma60 else None,
            "ma120": float(self.ma120) if self.ma120 else None,
            "boll_upper": float(self.boll_upper) if self.boll_upper else None,
            "boll_mid": float(self.boll_mid) if self.boll_mid else None,
            "boll_lower": float(self.boll_lower) if self.boll_lower else None,
            "dividend_info": self.dividend_info,
        }
