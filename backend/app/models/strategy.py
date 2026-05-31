from sqlalchemy import Column, Integer, String, Date, TIMESTAMP, JSON, Boolean
from sqlalchemy.sql import func

from app.utils.database import Base


class Strategy(Base):
    __tablename__ = "strategy"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String)
    params = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
