from sqlalchemy import Column, Integer, String, Date, TIMESTAMP, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.utils.database import Base


class SyncRecord(Base):
    __tablename__ = "sync_record"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sync_date = Column(Date, unique=True, nullable=False, index=True)
    stock_count = Column(Integer, default=0)
    status = Column(String(20), default="pending")
    start_time = Column(TIMESTAMP)
    end_time = Column(TIMESTAMP)
    error_msg = Column(String)
    success_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    no_data_count = Column(Integer, default=0)
    failed_stocks = Column(JSON)
    no_data_stocks = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())


class SelectionResult(Base):
    __tablename__ = "selection_result"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategy.id"), nullable=False)
    stock_code = Column(String(10), nullable=False, index=True)
    signal_date = Column(Date, nullable=False)
    signal_type = Column(String(50), nullable=False)
    signal_detail = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

    strategy = relationship("Strategy")
