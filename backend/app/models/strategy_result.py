from sqlalchemy import Column, Integer, String, Date, TIMESTAMP, JSON, Text
from sqlalchemy.sql import func

from app.utils.database import Base


class StrategyResult(Base):
    """保存选股策略的结果"""
    __tablename__ = "strategy_result"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    strategy_name = Column(String(50), nullable=False, index=True)
    run_date = Column(Date, nullable=False, index=True)
    params = Column(JSON)  # 策略运行时的参数
    total_count = Column(Integer, default=0)  # 符合条件的股票总数
    results = Column(JSON)  # 选股结果列表
    created_at = Column(TIMESTAMP, server_default=func.now())
