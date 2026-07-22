"""回测引擎：唯一持有完整历史数据的地方。

**防未来函数的四道闸**（改动本文件前请确认没有破坏其中任何一条）：

1. 规则只拿到 `bars[:i+1]` 切片，物理上够不到未来数据
2. 信号在 i 日收盘产生，**次日**成交（默认次日开盘）——用 i 日收盘价成交是
   业界称为 cheat-on-close 的作弊：收盘那一刻才算得出信号，已无法以该价成交
3. 出场判定只用收盘价，不用 high/low 去猜 bar 内路径
4. 一字涨停不可买、一字跌停不可卖——这是 A 股回测虚增收益最严重的单一来源
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from .base import (
    EXEC_NEXT_CLOSE, EXEC_NEXT_OPEN,
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
    """返回 (卖出原因, 是否可当日成交)；未触发返回 (None, False)。"""
    hits = []
    for rule, params in group.rules:
        try:
            reason = rule.should_exit(window, position, **params)
        except Exception:
            reason = None
        if reason:
            hits.append((rule, reason))
        elif group.logic == 'all':
            return None, False          # AND 语义下有一条不满足即整组不成立

    if not hits:
        return None, False
    if group.logic == 'all' and len(hits) != len(group.rules):
        return None, False

    # 当且仅当所有促成触发的规则都支持当日成交时，才当日尾盘卖出
    same_day = all(rule.meta.same_day_exec for rule, _ in hits)
    reason = ' + '.join(r for _, r in hits)
    return reason, same_day


def price_limit_pct(stock_code: str) -> float:
    """按板块返回涨跌幅限制。

    2026-07-06 起沪深主板 ST/*ST 涨跌幅由 5% 上调至 10%，与主板普通股统一，
    因此主板不再需要区分 ST。
    """
    if stock_code.startswith(('300', '301', '688')):
        return 20.0
    if stock_code.startswith(('8', '4', '9')):
        return 30.0
    return 10.0


def _is_one_word_board(bar) -> bool:
    """一字板：全天最高价等于最低价，说明从未打开过。"""
    if bar.high is None or bar.low is None:
        return False
    return float(bar.high) == float(bar.low)


def can_trade(bar, side: str, limit_pct: float) -> bool:
    """一字涨停买不到、一字跌停卖不掉；非一字的涨跌停盘中打开过，可成交。"""
    if bar.change_pct is None or not _is_one_word_board(bar):
        return True
    change = float(bar.change_pct)
    threshold = limit_pct - 0.5
    if side == 'buy' and change >= threshold:
        return False
    if side == 'sell' and change <= -threshold:
        return False
    return True


def _exec_price(bar, config: BacktestConfig) -> Optional[float]:
    price = bar.open if config.execution == EXEC_NEXT_OPEN else bar.close
    if price is None:
        price = bar.close
    return float(price) if price is not None else None


def evaluate_exits(groups: List[ExitGroup], window: List, position: Position):
    """按优先级返回第一个触发的出场原因。

    组已按「组内最高优先级规则」排好序，优先级：
    止损 > 移动止损 > 止盈 > MACD红柱连降 > 连续跌破均线 > 技术反转 > 时间到期。
    风控类无条件优先——同一根 bar 上止损和止盈都满足时，取悲观假设。
    """
    for group in groups:
        reason, same_day = _eval_group(group, window, position)
        if reason:
            return reason, same_day
    return None, False


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
    first_tradable_idx = min(start_idx, len(bars) - 1) if bars else 0
    prev_signal = False

    for i, bar in enumerate(bars):
        close = float(bar.close) if bar.close is not None else None

        # ---------- 1. 先撮合上一根 bar 挂出的委托（T+1 成交）----------
        if pending is not None and i > pending.signal_idx:
            if can_trade(bar, pending.side, limit):
                price = _exec_price(bar, config)
                if price:
                    if pending.side == 'buy' and position is None:
                        fill = cost.buy_price(price)
                        lots = int(cash // (fill * config.lot_size))
                        shares = lots * config.lot_size
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

            if position is not None and pending is None and i > position.entry_idx:
                # T+1：买入当日不可卖，故要求 i > entry_idx
                window = bars[:i + 1]
                reason, same_day = evaluate_exits(exit_groups, window, position)
                if reason:
                    if same_day and config.allow_same_day_exit() and can_trade(bar, 'sell', limit):
                        # 规则声明可盘中确认 → 当日尾盘按收盘价成交
                        trade, proceeds = _close_position(
                            position, close, bar, i, stock_code,
                            reason, entry_cost_paid, config,
                        )
                        cash += proceeds
                        trades.append(trade)
                        position = None
                        entry_cost_paid = 0.0
                    else:
                        pending = _Pending('sell', i, reason)
            elif position is None and pending is None:
                if signal and not prev_signal:      # 边沿检测
                    pending = _Pending('buy', i, '买入信号')

            prev_signal = signal

        # ---------- 4. 记录净值（按收盘价估值）----------
        mark = close if close is not None else (position.entry_price if position else 0.0)
        equity = cash + (position.shares * mark if position else 0.0)
        equity_curve.append((bar.trade_date, equity))

    # 期末仍持仓：按最后一根收盘价平仓，保证指标完整
    if position is not None and bars:
        last = bars[-1]
        price = float(last.close) if last.close is not None else position.entry_price
        trade, _ = _close_position(
            position, price, last, len(bars) - 1, stock_code,
            '回测结束平仓', entry_cost_paid, config,
        )
        trades.append(trade)

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
        total_bars=len(bars), benchmark_return_pct=benchmark,
        first_tradable_idx=first_tradable_idx,
    )
