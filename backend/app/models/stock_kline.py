from sqlalchemy import Column, Integer, String, Date, TIMESTAMP, DECIMAL, Index, UniqueConstraint
from sqlalchemy.sql import func

from app.utils.database import Base
from app.utils.sql_types import LenientJSON


class StockKline(Base):
    __tablename__ = "stock_kline"
    __table_args__ = (
        UniqueConstraint('stock_code', 'trade_date', name='uq_stock_kline_code_date'),
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
    boll_upper = Column(DECIMAL(10, 2))
    boll_mid = Column(DECIMAL(10, 2))
    boll_lower = Column(DECIMAL(10, 2))
    dif = Column(DECIMAL(10, 4))
    dea = Column(DECIMAL(10, 4))
    macd = Column(DECIMAL(10, 4))
    dividend_info = Column(LenientJSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # MACD / 涨跌幅等指标 0 是合法值，必须用 is not None 判空，否则会被吞成 null 导致图上断线
    _FLOAT_FIELDS = (
        "open", "high", "low", "close", "volume", "amount",
        "amplitude", "change_pct", "turnover_rate",
        "ma5", "ma10", "ma20", "ma30", "ma60",
        "boll_upper", "boll_mid", "boll_lower",
        "dif", "dea", "macd",
    )

    def to_dict(self):
        result = {
            "stock_code": self.stock_code,
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "dividend_info": self.dividend_info,
        }
        for field in self._FLOAT_FIELDS:
            value = getattr(self, field)
            result[field] = float(value) if value is not None else None
        return result
