"""跌破布林中轨出场（均值回归策略的常用止盈/止损位）。"""

from typing import List, Optional

from ..base import BaseExitRule, ExitMeta, Position


class BelowBollMidExit(BaseExitRule):
    meta = ExitMeta(
        name='below_boll_mid',
        display_name='跌破布林中轨',
        description='收盘价跌破布林带中轨即卖出',
        priority=50,
        same_day_exec=True,
        params=[],
    )

    def should_exit(self, bars: List, position: Position) -> Optional[str]:
        bar = bars[-1]
        if bar.close is None or bar.boll_mid is None:
            return None
        if float(bar.close) < float(bar.boll_mid):
            return '跌破布林中轨'
        return None


STRATEGY = BelowBollMidExit()
