from sqlalchemy import Column, Integer, String, DECIMAL, Date, Boolean, TIMESTAMP
from sqlalchemy.sql import func

from app.utils.database import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    market = Column(String(5), nullable=False)
    total_cap = Column(DECIMAL(20, 2))
    industry = Column(String(50))
    list_date = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "market": self.market,
            "total_cap": float(self.total_cap) if self.total_cap else None,
            "industry": self.industry,
            "list_date": self.list_date.isoformat() if self.list_date else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
