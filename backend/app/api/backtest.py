from datetime import date
from typing import List, Literal, Optional
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StrictBool, field_validator
from sqlalchemy.orm import Session

from app.utils.database import get_db
from app.utils.response import error, success
from app.services import backtest_service

router = APIRouter()


@router.get("/rules")
def get_rules():
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
    logic: Literal['any', 'all'] = 'any'
    rules: List[ExitRuleSpec] = Field(default_factory=list)


class BacktestConfigRequest(BaseModel):
    initial_capital: float = Field(default=100000, gt=0, allow_inf_nan=False)
    execution: Literal['next_close'] = 'next_close'
    exit_timing: Literal['next_day'] = 'next_day'
    check_price_limit: StrictBool = True
    commission_rate: float = Field(default=0.00025, ge=0, lt=1, allow_inf_nan=False)
    min_commission: float = Field(default=5, ge=0, allow_inf_nan=False)
    stamp_tax_rate: float = Field(default=0.0005, ge=0, lt=1, allow_inf_nan=False)
    transfer_fee_rate: float = Field(default=0.00001, ge=0, lt=1, allow_inf_nan=False)
    slippage_rate: float = Field(default=0.001, ge=0, lt=1, allow_inf_nan=False)


class BacktestRequest(BaseModel):
    stock_codes: List[str] = Field(..., min_length=1)
    entry_name: str
    entry_params: dict = Field(default_factory=dict)
    exit_groups: List[ExitGroupSpec] = Field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    config: BacktestConfigRequest = Field(default_factory=BacktestConfigRequest)

    @field_validator('stock_codes')
    @classmethod
    def validate_stock_codes(cls, codes):
        codes = list(dict.fromkeys(code.strip() for code in codes))
        if any(re.fullmatch(r'[0-9]{6}', code) is None for code in codes):
            raise ValueError('股票代码必须为六位数字')
        if len(codes) > backtest_service.MAX_BACKTEST_STOCKS:
            raise ValueError(f'单次最多回测 {backtest_service.MAX_BACKTEST_STOCKS} 只股票')
        return codes


@router.post("/run")
def run_backtest(request: BacktestRequest, db: Session = Depends(get_db)):
    """对选定股票执行回测（每只票独立满仓，再横向聚合）"""
    result = backtest_service.run(
        db,
        stock_codes=request.stock_codes,
        entry_name=request.entry_name,
        entry_params=request.entry_params,
        exit_groups=[g.model_dump() for g in request.exit_groups],
        start_date=request.start_date,
        end_date=request.end_date,
        config_raw=request.config.model_dump(),
    )
    if 'error' in result:
        return error(code=1, msg=result['error'])
    return success(data=result)
