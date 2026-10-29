"""连续跌破均线：连续 N 天收在 MA5 之下，或连续 M 天收在 MA10 之下。

动机：单日跌破均线噪音太大（尤其 MA5），连续多日站不回去才说明短期趋势真的走坏。
两条腿是 OR 关系——MA5 反应快但需要更多天确认，MA10 更慢但两天即可确认。

任一参数设为 0 即关闭该条腿。
"""

from typing import List, Optional

from app.services.strategies.base import ParamSpec
from ..base import BaseExitRule, ExitMeta, Position


def _streak_below(bars: List, field: str, days: int) -> bool:
    """最近 days 根 bar 是否全部收在指定均线之下。"""
    if days <= 0 or len(bars) < days:
        return False
    for bar in bars[-days:]:
        ma = getattr(bar, field, None)
        if ma is None or bar.close is None:
            return False
        if float(bar.close) >= float(ma):
            return False
    return True


class BelowMaStreakExit(BaseExitRule):
    meta = ExitMeta(
        name='below_ma_streak',
        display_name='连续跌破均线',
        description='连续 N 天跌破 MA5，或连续 M 天跌破 MA10',
        priority=45,
        params=[
            ParamSpec('ma5_days', '连续', 3, '天跌破 MA5（0=关闭）', minimum=0, maximum=20),
            ParamSpec('ma10_days', '或连续', 2, '天跌破 MA10（0=关闭）', minimum=0, maximum=20),
        ],
    )

    def should_exit(
        self, bars: List, position: Position, ma5_days: int = 3, ma10_days: int = 2
    ) -> Optional[str]:
        if _streak_below(bars, 'ma5', ma5_days):
            return f'连续{ma5_days}天跌破MA5'
        if _streak_below(bars, 'ma10', ma10_days):
            return f'连续{ma10_days}天跌破MA10'
        return None


STRATEGY = BelowMaStreakExit()
