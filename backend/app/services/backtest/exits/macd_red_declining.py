"""MACD 红柱见顶回落：从红柱最高点开始连续下降第 N 天卖出。

动机：MACD 柱是 `2×(DIF-DEA)`，红柱走高代表多头动能在加速。红柱见顶后连续
缩短意味着上涨动能衰竭——虽然价格可能还在涨，但推动力在减弱，是典型的顶背离前兆。

判定（以 decline_days=3 为例，bar 下标从右往左）：
    macd[-4] 是峰值且为红柱（>0 且不低于前一根）
    macd[-3] < macd[-4]，macd[-2] < macd[-3]，macd[-1] < macd[-2]   连续 3 天下降
    → 在第 3 个下降日发出卖出信号

峰值本身要求为红柱，但下降过程中转绿不影响触发——那只会是更强的卖出理由。
"""

from typing import List, Optional

from app.services.strategies.base import ParamSpec
from ..base import BaseExitRule, ExitMeta, Position


class MacdRedDecliningExit(BaseExitRule):
    meta = ExitMeta(
        name='macd_red_declining',
        display_name='MACD红柱连降',
        description='MACD 红柱见顶后，连续下降第 N 天卖出',
        priority=40,
        same_day_exec=True,
        params=[ParamSpec('decline_days', '连续下降', 3, '天后卖出', minimum=1, maximum=10)],
    )

    def should_exit(self, bars: List, position: Position, decline_days: int = 3) -> Optional[str]:
        # 需要：decline_days 个下降日 + 峰值 + 峰值前一根（用于确认峰值）
        need = decline_days + 2
        if len(bars) < need:
            return None

        window = bars[-need:]
        macd = [b.macd for b in window]
        if any(m is None for m in macd):
            return None
        macd = [float(m) for m in macd]

        before_peak, peak = macd[0], macd[1]
        declining = macd[1:]                      # 峰值 + 其后的下降序列

        # 峰值必须是红柱，且确实是个局部高点
        if peak <= 0 or peak < before_peak:
            return None

        # 峰值之后必须逐日严格下降
        for prev, curr in zip(declining, declining[1:]):
            if curr >= prev:
                return None

        return f'MACD红柱连降{decline_days}天(峰值{peak:.4f}→{macd[-1]:.4f})'


STRATEGY = MacdRedDecliningExit()
