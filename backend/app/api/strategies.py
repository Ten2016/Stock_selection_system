from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from decimal import Decimal

from app.utils.database import get_db
from app.utils.response import success, error
from app.services import strategy_service
from app.models.strategy_result import StrategyResult

router = APIRouter()


def convert_decimals(obj):
    """递归将 Decimal 转为 float（JSON 列写库前需要）"""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    return obj


@router.get("")
def get_strategies():
    """返回策略清单，含各策略的参数声明（前端据此动态渲染表单）"""
    return success(data=strategy_service.get_available_strategies())


@router.get("/latest-result")
def get_latest_strategy_result(
    strategy_name: str = Query(..., description="策略名称"),
    db: Session = Depends(get_db)
):
    """获取指定策略的最新一次运行结果"""
    result = db.query(StrategyResult).filter(
        StrategyResult.strategy_name == strategy_name
    ).order_by(StrategyResult.created_at.desc(), StrategyResult.id.desc()).first()

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
def select_stocks(
    request: Request,
    strategy_name: str = Query(..., description="策略名称"),
    min_market_cap: Optional[float] = Query(None, ge=0, allow_inf_nan=False, description="最小市值（亿元）"),
    db: Session = Depends(get_db)
):
    """运行全市场选股。

    策略专属参数不在此显式声明——由策略自己的 ParamSpec 从 query string 中解析，
    因此新增策略无需改动本接口。
    """
    try:
        params = strategy_service.coerce_params(strategy_name, dict(request.query_params))
        results = strategy_service.run_strategy(
            db, strategy_name, min_market_cap=min_market_cap, params=params
        )
    except ValueError as exc:
        return error(code=1, msg=str(exc))

    db.query(StrategyResult).filter(
        StrategyResult.strategy_name == strategy_name
    ).delete()

    db.add(StrategyResult(
        strategy_name=strategy_name,
        run_date=date.today(),
        params={"min_market_cap": min_market_cap, **params},
        total_count=len(results),
        results=convert_decimals(results),
    ))
    db.commit()

    return success(data={
        "strategy_name": strategy_name,
        "selected_stocks": convert_decimals(results),
        "total_count": len(results),
    })


@router.get("/backtest")
def backtest_strategy(
    request: Request,
    strategy_name: str = Query(..., description="策略名称"),
    stock_code: str = Query(..., description="股票代码"),
    start_year: int = Query(2020, ge=1900, le=9999, description="回测起始年份"),
    db: Session = Depends(get_db)
):
    """回测单只股票的策略，返回历史所有买点"""
    try:
        params = strategy_service.coerce_params(strategy_name, dict(request.query_params))
        result = strategy_service.backtest_strategy(
            db, stock_code, strategy_name, start_year=start_year, params=params
        )
    except ValueError as exc:
        return error(code=1, msg=str(exc))
    return success(data=convert_decimals(result))
