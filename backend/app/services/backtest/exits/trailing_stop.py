"""移动止损：从持仓期最高**收盘价**回撤指定幅度即卖出。

锚点用收盘价而非最高价：用 high 更新锚点、再用 low 判触发，隐含「同一根 bar 内
先涨后跌」的路径假设——若实际先跌后涨，会产生本不该发生的止损。这是移动止损在
日线上最主要的偏差源。全用 close 则锚点与触发同源，无路径假设。
"""

from typing import List, Optional

from app.services.strategies.base import ParamSpec
from ..base import BaseExitRule, ExitMeta, Position


class TrailingStopExit(BaseExitRule):
    meta = ExitMeta(
        name='trailing_stop',
        display_name='移动止损',
        description='从持仓期最高收盘价回撤达到阈值即卖出',
        priority=20,
        same_day_exec=True,
        params=[ParamSpec('drawdown_pct', '回撤达', 10.0, '% 卖出',
                          param_type='float', minimum=0.5, maximum=50, step=0.5)],
    )

    def should_exit(self, bars: List, position: Position, drawdown_pct: float = 10.0) -> Optional[str]:
        peak = position.highest_close
        if not peak:
            return None
        close = float(bars[-1].close)
        dd = (close - peak) / peak * 100
        if dd <= -drawdown_pct:
            return f'移动止损(自{peak:.2f}回撤{dd:.1f}%)'
        return None


STRATEGY = TrailingStopExit()
