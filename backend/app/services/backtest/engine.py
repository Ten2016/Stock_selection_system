"""回测引擎：唯一持有完整历史数据的地方。

**防未来函数的四道闸**（改动本文件前请确认没有破坏其中任何一条）：

1. 规则只拿到 `bars[:i+1]` 切片，物理上够不到未来数据
2. 买卖信号在 i 日收盘产生，下一个交易日收盘撮合，不能使用信号日价格成交
3. 出场判定只用收盘价，不用 high/low 去猜 bar 内路径
4. 收盘涨停不可买、收盘跌停不可卖；期末持仓仅估值，不强制成交
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .base import (
    BacktestConfig, BaseExitRule, Position, Trade,
)


@dataclass
class _Pending:
    side: str          # 'buy' | 'sell'
    signal_idx: int
    reason: str


@dataclass
class ExitGroup:
    """一组卖出规则。组内按 logic 合并，组间恒为 OR（任一组满足即卖出）。

    这是析取范式（OR of ANDs），可以表达任意布尔组合：
      - 单组 any  → A OR B OR C
      - 单组 all  → A AND B AND C
      - 多组      → (A AND B) OR C
    """
    logic: str                      # 'any' | 'all'
    rules: List[Tuple[BaseExitRule, dict]]


def _eval_group(group: ExitGroup, window: List, position: Position):
    """返回卖出原因，未触发返回 None。"""
    hits = []
    for rule, params in group.rules:
        reason = rule.should_exit(window, position, **params)
        if reason:
            hits.append((rule, reason))
        elif group.logic == 'all':
            return None

    if not hits:
        return None
    if group.logic == 'all' and len(hits) != len(group.rules):
        return None

    reason = ' + '.join(r for _, r in hits)
    return reason


def price_limit_pct(stock_code: str) -> float:
    """按代码前缀使用固定涨跌幅假设，不区分历史日期。"""
    if stock_code.startswith(('300', '301', '688')):
        return 20.0
    if stock_code.startswith(('8', '4', '9')):
        return 30.0
    return 10.0


def can_trade(bar, side: str, limit_pct: float) -> bool:
    """按收盘涨跌幅保守过滤，不能用盘中打开过证明收盘可成交。"""
    if bar.change_pct is None:
        return False
    change = float(bar.change_pct)
    threshold = limit_pct - 0.5
    if side == 'buy' and change >= threshold:
        return False
    if side == 'sell' and change <= -threshold:
        return False
    return True


def _exec_price(bar) -> Optional[float]:
    if bar.volume is None or float(bar.volume) <= 0:
        return None
    price = bar.close
    return float(price) if price is not None else None


def evaluate_exits(groups: List[ExitGroup], window: List, position: Position):
    """按优先级返回第一个触发的出场原因。

    组已按「组内最高优先级规则」排好序，优先级：
    止损 > 移动止损 > 止盈 > MACD红柱连降 > 连续跌破均线 > 技术反转 > 时间到期。
    风控类无条件优先——同一根 bar 上止损和止盈都满足时，取悲观假设。
    """
    for group in groups:
        reason = _eval_group(group, window, position)
        if reason:
            return reason
    return None


@dataclass
class BacktestResult:
    stock_code: str
    stock_name: str
    trades: List[Trade]
    equity_curve: List[Tuple[object, float]]     # [(trade_date, 权益)]
    exposure_bars: int                            # 持仓 bar 数，用于算仓位暴露
    total_bars: int
    benchmark_return_pct: Optional[float]         # 同期买入持有收益率
    first_tradable_idx: int
    open_position: Optional[dict] = None


def _close_position(
    position: Position, price: float, bar, idx: int,
    stock_code: str, reason: str, entry_fee: float, config: BacktestConfig,
) -> Tuple[Trade, float]:
    """按给定价格平仓，返回 (成交记录, 回笼现金)。"""
    cost = config.cost
    fill = cost.sell_price(price)
    amount = position.shares * fill
    fee = cost.sell_cost(amount)
    gross = (fill - position.entry_price) * position.shares
    total_cost = entry_fee + fee
    buy_amount = position.entry_price * position.shares
    trade = Trade(
        stock_code=stock_code,
        entry_date=position.entry_date, entry_price=position.entry_price,
        exit_date=bar.trade_date, exit_price=fill,
        shares=position.shares, exit_reason=reason,
        bars_held=position.bars_held(idx),
        gross_pnl=gross, cost=total_cost, pnl=gross - total_cost,
        pnl_pct=(gross - total_cost) / buy_amount * 100 if buy_amount else 0.0,
    )
    return trade, amount - fee


def run_backtest(
    stock_code: str,
    stock_name: str,
    bars: List,
    entry_signal_dates: set,
    exit_groups: List[ExitGroup],
    config: BacktestConfig,
    warmup: int = 0,
) -> BacktestResult:
    """对单只股票执行回测。

    `entry_signal_dates` 是买入条件在哪些交易日成立（由买入规则预先算好，
    其本身已保证无未来函数）。引擎在此基础上做**边沿检测**——只在
    「昨天不成立、今天成立」时买入，避免状态型条件（如「站上 60 日线」，
    命中率可达 48%）被当成每日买点。
    """
    cost = config.cost
    limit = price_limit_pct(stock_code)

    cash = config.initial_capital
    position: Optional[Position] = None
    pending: Optional[_Pending] = None
    trades: List[Trade] = []
    equity_curve: List[Tuple[object, float]] = []
    exposure_bars = 0
    entry_cost_paid = 0.0

    start_idx = max(warmup, 1)
    first_tradable_idx = start_idx
    prev_signal = False

    for i, bar in enumerate(bars):
        if i < warmup:
            continue
        close = float(bar.close) if bar.close is not None else None

        # ---------- 1. 按本日收盘价撮合此前挂出的委托 ----------
        if pending is not None and i > pending.signal_idx:
            if not config.check_price_limit or can_trade(bar, pending.side, limit):
                price = _exec_price(bar)
                if price is not None and price > 0:
                    if pending.side == 'buy' and position is None:
                        fill = cost.buy_price(price)
                        lots = int(cash // (fill * config.lot_size))
                        shares = lots * config.lot_size
                        while shares > 0 and shares * fill + cost.buy_cost(shares * fill) > cash:
                            shares -= config.lot_size
                        if shares > 0:
                            amount = shares * fill
                            fee = cost.buy_cost(amount)
                            if amount + fee <= cash:
                                cash -= amount + fee
                                entry_cost_paid = fee
                                position = Position(
                                    entry_idx=i, entry_date=bar.trade_date,
                                    entry_price=fill, shares=shares,
                                    highest_close=close or fill,
                                )
                        pending = None
                    elif pending.side == 'sell' and position is not None:
                        trade, proceeds = _close_position(
                            position, price, bar, i, stock_code,
                            pending.reason, entry_cost_paid, config,
                        )
                        cash += proceeds
                        trades.append(trade)
                        position = None
                        entry_cost_paid = 0.0
                        pending = None
                    else:
                        pending = None
            # 不可成交则保留 pending，下一根 bar 继续尝试

        # ---------- 2. 更新持仓状态 ----------
        if position is not None:
            exposure_bars += 1
            if close is not None and close > position.highest_close:
                position.highest_close = close

        # ---------- 3. 产生本 bar 的信号（只看 bars[:i+1]）----------
        if i >= start_idx and close is not None:
            signal = bar.trade_date.isoformat() in entry_signal_dates

            if position is not None and pending is None:
                window = bars[:i + 1]
                reason = evaluate_exits(exit_groups, window, position)
                if reason:
                    pending = _Pending('sell', i, reason)
            elif position is None and pending is None:
                if signal and not prev_signal:      # 边沿检测
                    pending = _Pending('buy', i, '买入信号')

            prev_signal = signal

        # ---------- 4. 记录净值（按收盘价估值）----------
        mark = close if close is not None else (position.entry_price if position else 0.0)
        equity = cash + (position.shares * mark if position else 0.0)
        equity_curve.append((bar.trade_date, equity))

    open_position = None
    if position is not None and bars:
        last = bars[-1]
        price = float(last.close) if last.close is not None else position.entry_price
        open_position = {
            'entry_date': position.entry_date.isoformat(),
            'entry_price': position.entry_price,
            'shares': position.shares,
            'mark_price': price,
            'market_value': position.shares * price,
            'entry_fee': entry_cost_paid,
            'unrealized_pnl': (price - position.entry_price) * position.shares - entry_cost_paid,
            'pending_exit': pending.reason if pending and pending.side == 'sell' else None,
        }

    # 基准：同期买入持有。起点必须与策略实际能开始交易的 bar 对齐，
    # 否则预热期的涨跌会被错误计入基准。
    benchmark = None
    if bars and first_tradable_idx < len(bars):
        base = bars[first_tradable_idx].close
        final = bars[-1].close
        if base and final:
            benchmark = (float(final) - float(base)) / float(base) * 100

    return BacktestResult(
        stock_code=stock_code, stock_name=stock_name, trades=trades,
        equity_curve=equity_curve, exposure_bars=exposure_bars,
        total_bars=len(equity_curve), benchmark_return_pct=benchmark,
        first_tradable_idx=first_tradable_idx,
        open_position=open_position,
    )
