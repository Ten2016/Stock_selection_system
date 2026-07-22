"""固定百分比止盈。"""

from typing import List, Optional

from app.services.strategies.base import ParamSpec
from ..base import BaseExitRule, ExitMeta, Position


class TakeProfitExit(BaseExitRule):
    meta = ExitMeta(
        name='take_profit',
        display_name='止盈',
        description='收盘价相对成本价涨幅达到阈值即卖出',
        priority=30,
        same_day_exec=True,
        params=[ParamSpec('profit_pct', '盈利达', 15.0, '% 止盈',
                          param_type='float', minimum=0.5, maximum=200, step=0.5)],
    )

    def should_exit(self, bars: List, position: Position, profit_pct: float = 15.0) -> Optional[str]:
        ret = position.return_pct(float(bars[-1].close))
        if ret >= profit_pct:
            return f'止盈({ret:.1f}%)'
        return None


STRATEGY = TakeProfitExit()
