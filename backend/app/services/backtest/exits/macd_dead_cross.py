"""MACD 死叉出场：DIF 由上向下穿越 DEA。"""

from typing import List, Optional

from ..base import BaseExitRule, ExitMeta, Position


class MacdDeadCrossExit(BaseExitRule):
    meta = ExitMeta(
        name='macd_dead_cross',
        display_name='MACD死叉',
        description='DIF 下穿 DEA 即卖出',
        priority=50,
        params=[],
    )

    def should_exit(self, bars: List, position: Position) -> Optional[str]:
        if len(bars) < 2:
            return None
        curr, prev = bars[-1], bars[-2]
        if None in (curr.dif, curr.dea, prev.dif, prev.dea):
            return None
        # 前一日在上方或持平，当日跌到下方 → 死叉
        if float(prev.dif) >= float(prev.dea) and float(curr.dif) < float(curr.dea):
            return 'MACD死叉'
        return None


STRATEGY = MacdDeadCrossExit()
