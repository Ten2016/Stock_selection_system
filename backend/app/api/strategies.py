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
    db: Session = Depends(get_db)
):
    results = strategy_service.run_strategy(db, strategy_name, min_market_cap=min_market_cap)
    return success(data={
        "strategy_name": strategy_name,
        "selected_stocks": results,
        "total_count": len(results)
    })
