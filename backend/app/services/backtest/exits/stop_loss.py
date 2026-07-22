"""固定百分比止损。

⚠️ 学术警告（Kaminski & Lo, JFM 2014）：随机游走下止损**必然降低**期望收益，
只有存在动量时才创造价值。A 股日线短期反转强于动量，紧止损（<5%）很可能是负贡献。
止损应被当作风险管理工具（看回撤/Calmar）而非收益增强器（看总收益）。
"""

from typing import List, Optional

from app.services.strategies.base import ParamSpec
from ..base import BaseExitRule, ExitMeta, Position


class StopLossExit(BaseExitRule):
    meta = ExitMeta(
        name='stop_loss',
        display_name='止损',
        description='收盘价相对成本价跌幅达到阈值即卖出',
        priority=10,
        same_day_exec=True,
        params=[ParamSpec('loss_pct', '亏损达', 8.0, '% 止损',
                          param_type='float', minimum=0.5, maximum=50, step=0.5)],
    )

    def should_exit(self, bars: List, position: Position, loss_pct: float = 8.0) -> Optional[str]:
        ret = position.return_pct(float(bars[-1].close))
        if ret <= -loss_pct:
            return f'止损({ret:.1f}%)'
        return None


STRATEGY = StopLossExit()
