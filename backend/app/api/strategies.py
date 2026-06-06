from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from decimal import Decimal

from app.utils.database import get_db
from app.utils.response import success, error
from app.services import strategy_service
from app.models.strategy_result import StrategyResult


def convert_decimals(obj):
    """递归将 Decimal 转为 float"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    return obj

router = APIRouter()


@router.get("")
async def get_strategies():
    strategies = strategy_service.get_available_strategies()
    return success(data=strategies)


@router.get("/latest-result")
async def get_latest_strategy_result(
    strategy_name: str = Query(..., description="策略名称"),
    db: Session = Depends(get_db)
):
    """获取指定策略的最新一次运行结果"""
    result = db.query(StrategyResult).filter(
        StrategyResult.strategy_name == strategy_name
    ).order_by(StrategyResult.run_date.desc()).first()
    
    if result:
        return success(data={
            "strategy_name": result.strategy_name,
            "run_date": result.run_date.isoformat() if result.run_date else None,
            "params": result.params,
            "selected_stocks": result.results or [],
            "total_count": result.total_count,
        })
    return success(data={
        "strategy_name": strategy_name,
        "run_date": None,
        "params": None,
        "selected_stocks": [],
        "total_count": 0,
    })


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
    
    # 只有运行成功且有结果时，才更新数据库（避免更新失败丢失历史数据）
    if results and len(results) > 0:
        # 删除旧结果，只保留最新
        db.query(StrategyResult).filter(
            StrategyResult.strategy_name == strategy_name
        ).delete()
        
        params = {
            "min_market_cap": min_market_cap,
            "x_days": x_days,
            "y_days": y_days,
            "z_days": z_days,
            "y_pct": y_pct,
        }
        
        new_result = StrategyResult(
            strategy_name=strategy_name,
            run_date=date.today(),
            params=params,
            total_count=len(results),
            results=convert_decimals(results),
        )
        db.add(new_result)
        db.commit()
    
    return success(data={
        "strategy_name": strategy_name,
        "selected_stocks": results,
        "total_count": len(results)
    })
