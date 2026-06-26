from pydantic import BaseModel
from typing import Optional
from datetime import date


class StockBasicBase(BaseModel):
    code: str
    name: str
    market: str
    total_cap: Optional[float] = None
    industry: Optional[str] = None
    list_date: Optional[date] = None


class StockBasicCreate(StockBasicBase):
    pass


class StockBasicUpdate(BaseModel):
    total_cap: Optional[float] = None
    industry: Optional[str] = None
    is_active: Optional[bool] = None


class StockBasicOut(StockBasicBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class KlineData(BaseModel):
    stock_code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    amount: Optional[float] = None
    amplitude: Optional[float] = None
    change_pct: Optional[float] = None
    turnover_rate: Optional[float] = None
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma30: Optional[float] = None
    ma60: Optional[float] = None
    boll_upper: Optional[float] = None
    boll_mid: Optional[float] = None
    boll_lower: Optional[float] = None
    dif: Optional[float] = None
    dea: Optional[float] = None
    macd: Optional[float] = None
