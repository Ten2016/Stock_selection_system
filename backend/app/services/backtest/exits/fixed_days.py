"""固定持有期出场。

最简单、参数最不容易过拟合的出场规则。调研建议把它当**基准线**而非策略：
先跑 N=1/3/5/10/20 的纯时间退出，得到选股信号的天然收益衰减曲线，
之后任何复杂出场规则必须跑赢这条线才有资格采用。
"""

from typing import List, Optional

from app.services.strategies.base import ParamSpec
from ..base import BaseExitRule, ExitMeta, Position


class FixedDaysExit(BaseExitRule):
    meta = ExitMeta(
        name='fixed_days',
        display_name='固定持有期',
        description='持有满 N 个交易日后无条件卖出',
        priority=90,
        params=[ParamSpec('hold_days', '持有', 5, '个交易日', minimum=1, maximum=250)],
    )

    def should_exit(self, bars: List, position: Position, hold_days: int = 5) -> Optional[str]:
        held = position.bars_held(len(bars) - 1)
        if held >= hold_days:
            return f'持有满{hold_days}日'
        return None


STRATEGY = FixedDaysExit()
