"""回测框架。

- `exits/`   出场规则（每个一文件，注册表自动发现）
- `engine`   逐 bar 状态机，唯一持有完整数据的地方
- `metrics`  指标计算
- 入场条件直接复用 `services/strategies/` 的选股策略，不重复定义
"""

from .base import (
    EXEC_NEXT_CLOSE, EXEC_NEXT_OPEN, EXIT_NEXT_DAY, EXIT_SAME_DAY,
    BacktestConfig, BaseExitRule, ExitMeta, Position, Trade, TradeCost,
)
from .engine import BacktestResult, ExitGroup, price_limit_pct, run_backtest
from .exits import all_exit_rules, get_exit_rule
from .metrics import aggregate, summarize

__all__ = [
    'EXEC_NEXT_OPEN', 'EXEC_NEXT_CLOSE', 'EXIT_SAME_DAY', 'EXIT_NEXT_DAY',
    'BacktestConfig', 'BaseExitRule', 'ExitMeta', 'Position', 'Trade', 'TradeCost',
    'BacktestResult', 'ExitGroup', 'run_backtest', 'price_limit_pct',
    'all_exit_rules', 'get_exit_rule',
    'summarize', 'aggregate',
]
