from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.utils.database import get_db
from app.utils.response import error, success
from app.services import backtest_service

router = APIRouter()


@router.get("/rules")
async def get_rules():
    """买入条件与卖出规则清单（含参数声明，前端据此动态渲染表单）"""
    return success(data={
        'entry_rules': backtest_service.get_entry_rules(),
        'exit_rules': backtest_service.get_exit_rules(),
    })


class ExitRuleSpec(BaseModel):
    name: str
    params: dict = Field(default_factory=dict)


class ExitGroupSpec(BaseModel):
    """一组卖出规则：组内按 logic 合并，组间恒为 OR。"""
    logic: str = 'any'                 # 'any' = 任一满足 | 'all' = 全部满足
    rules: List[ExitRuleSpec] = Field(default_factory=list)


class BacktestRequest(BaseModel):
    stock_codes: List[str] = Field(..., min_length=1)
    entry_name: str
    entry_params: dict = Field(default_factory=dict)
    exit_groups: List[ExitGroupSpec] = Field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    config: dict = Field(default_factory=dict)


@router.post("/run")
async def run_backtest(request: BacktestRequest, db: Session = Depends(get_db)):
    """对选定股票执行回测（每只票独立满仓，再横向聚合）"""
    result = backtest_service.run(
        db,
        stock_codes=request.stock_codes,
        entry_name=request.entry_name,
        entry_params=request.entry_params,
        exit_groups=[g.model_dump() for g in request.exit_groups],
        start_date=request.start_date,
        end_date=request.end_date,
        config_raw=request.config,
    )
    if 'error' in result:
        return error(code=1, msg=result['error'])
    return success(data=result)
