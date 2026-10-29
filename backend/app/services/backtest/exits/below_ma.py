"""跌破均线出场（技术指标反转）。

与买入条件天然对称：`consecutive_ma5` 站上均线买入，跌破均线卖出。
这是「入场 × 出场自由组合」最直接的收益点。
"""

from typing import List, Optional

from app.services.strategies.base import ParamSpec
from ..base import BaseExitRule, ExitMeta, Position

# 只有这几条均线有预存列
_MA_FIELDS = {5: 'ma5', 10: 'ma10', 20: 'ma20', 30: 'ma30', 60: 'ma60'}


class BelowMaExit(BaseExitRule):
    meta = ExitMeta(
        name='below_ma',
        display_name='跌破均线',
        description='收盘价跌破指定日均线即卖出',
        priority=50,
        params=[ParamSpec('ma_period', '跌破', 20, '日均线', minimum=5, maximum=60, step=5)],
    )

    def should_exit(self, bars: List, position: Position, ma_period: int = 20) -> Optional[str]:
        field = _MA_FIELDS.get(ma_period)
        bar = bars[-1]
        if field is not None:
            ma = getattr(bar, field, None)
        else:
            if len(bars) < ma_period:
                return None
            closes = [b.close for b in bars[-ma_period:]]
            if any(close is None for close in closes):
                return None
            ma = sum(float(close) for close in closes) / ma_period
        if ma is None or bar.close is None:
            return None
        if float(bar.close) < float(ma):
            return f'跌破MA{ma_period}'
        return None


STRATEGY = BelowMaExit()
