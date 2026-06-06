from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.utils.database import get_db
from app.utils.response import success
from app.services import strategy_service

router = APIRouter()


@router.get("")
async def get_strategies():
    strategies = strategy_service.get_available_strategies()
    return success(data=strategies)


@router.post("/select")
async def select_stocks(
    strategy_name: str = Query(..., description="策略名称"),
    min_market_cap: Optional[float] = Query(None, description="最小市值（亿元）"),
    x_days: int = Query(30, description="往前找x天"),
    y_days: int = Query(10, description="之后y天内（用于consecutive_ma5策略）"),
    z_days: int = Query(2, description="连续z天"),
    y_pct: float = Query(5.0, description="涨幅大于y%（用于rise_then_fall策略）"),
    db: Session = Depends(get_db)
):
    results = strategy_service.run_strategy(
        db,
        strategy_name,
        min_market_cap=min_market_cap,
        x_days=x_days,
        y_days=y_days,
        z_days=z_days,
        y_pct=y_pct
    )
    return success(data={
        "strategy_name": strategy_name,
        "selected_stocks": results,
        "total_count": len(results)
    })
