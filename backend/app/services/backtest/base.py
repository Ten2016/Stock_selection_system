"""回测基础设施：持仓、成交、成本、出场规则基类。

出场规则与买入条件（`services/strategies/`）是两套独立的规则，回测时做笛卡尔积组合。
参数声明复用 strategies.base 的 ParamSpec，前端表单机制零改动。
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from app.services.strategies.base import ParamSpec

EXEC_NEXT_CLOSE = 'next_close'
EXIT_NEXT_DAY = 'next_day'


@dataclass
class TradeCost:
    """整个回测区间统一使用的交易成本。"""

    commission_rate: float = 0.00025      # 佣金 万2.5，双边
    min_commission: float = 5.0           # 单笔最低佣金
    stamp_tax_rate: float = 0.0005        # 印花税 万5，仅卖出
    transfer_fee_rate: float = 0.00001    # 过户费 0.001%，双边
    slippage_rate: float = 0.001          # 滑点，双边

    def buy_cost(self, amount: float) -> float:
        return max(amount * self.commission_rate, self.min_commission) + amount * self.transfer_fee_rate

    def sell_cost(self, amount: float) -> float:
        return (
            max(amount * self.commission_rate, self.min_commission)
            + amount * self.transfer_fee_rate
            + amount * self.stamp_tax_rate
        )

    def buy_price(self, price: float) -> float:
        return price * (1 + self.slippage_rate)

    def sell_price(self, price: float) -> float:
        return price * (1 - self.slippage_rate)


@dataclass
class BacktestConfig:
    initial_capital: float = 100_000.0
    execution: str = EXEC_NEXT_CLOSE
    exit_timing: str = EXIT_NEXT_DAY
    check_price_limit: bool = True        # 收盘涨停不买、收盘跌停不卖
    lot_size: int = 100                   # A 股一手 100 股
    cost: TradeCost = field(default_factory=TradeCost)

    def __post_init__(self):
        if self.execution != EXEC_NEXT_CLOSE or self.exit_timing != EXIT_NEXT_DAY:
            raise ValueError('买卖统一使用信号次一交易日收盘价成交')


@dataclass
class Position:
    entry_idx: int
    entry_date: date
    entry_price: float                    # 实际成交价（含滑点）
    shares: int
    highest_close: float                  # 持仓期最高收盘价，供移动止损用

    def bars_held(self, current_idx: int) -> int:
        """已持有的交易日数（bar 数）。

        用 bar 数而非自然日：A 股跨春节持仓按自然日会多算约 9 天。
        """
        return current_idx - self.entry_idx

    def return_pct(self, price: float) -> float:
        if not self.entry_price:
            return 0.0
        return (price - self.entry_price) / self.entry_price * 100


@dataclass
class Trade:
    stock_code: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    shares: int
    exit_reason: str
    bars_held: int
    gross_pnl: float                      # 不含费用
    cost: float                           # 买入+卖出全部费用
    pnl: float                            # 含费用净盈亏
    pnl_pct: float                        # 相对买入市值的净收益率

    def to_dict(self) -> dict:
        return {
            'stock_code': self.stock_code,
            'entry_date': self.entry_date.isoformat(),
            'entry_price': round(self.entry_price, 3),
            'exit_date': self.exit_date.isoformat(),
            'exit_price': round(self.exit_price, 3),
            'shares': self.shares,
            'exit_reason': self.exit_reason,
            'bars_held': self.bars_held,
            'gross_pnl': round(self.gross_pnl, 2),
            'cost': round(self.cost, 2),
            'pnl': round(self.pnl, 2),
            'pnl_pct': round(self.pnl_pct, 2),
        }


@dataclass(frozen=True)
class ExitMeta:
    name: str
    display_name: str
    description: str
    priority: int                         # 数字越小越优先（同 bar 多个触发时取最优先的）
    params: List[ParamSpec] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'priority': self.priority,
            'params': [p.to_dict() for p in self.params],
        }


class BaseExitRule:
    """出场规则基类。

    `should_exit()` 只能看到 `bars[:i+1]`（引擎保证），加上持仓上下文。
    返回卖出原因字符串表示触发，返回 None 表示继续持有。

    **所有判定只用收盘价**：日线只有 OHLC，不告诉你 high 和 low 谁先发生，
    用 low 判止损隐含「先跌后涨」的路径假设。实测有 18% 的 bar 是路径歧义的，
    在无 tick 数据时没有可证明正确的解法。只用 close 判定零歧义、零路径假设。
    """

    meta: ExitMeta

    def should_exit(self, bars: List, position: Position, **params) -> Optional[str]:
        raise NotImplementedError

    def defaults(self) -> Dict[str, Any]:
        return {p.name: p.default for p in self.meta.params}

    def coerce_params(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        return {p.name: p.coerce(raw.get(p.name)) for p in self.meta.params}
