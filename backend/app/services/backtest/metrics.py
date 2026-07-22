"""回测指标计算。

口径依据（均来自 empyrical / backtesting.py 源码，非自创）：
- 年化用**交易日**折算：`(1+total)^(252/N) - 1`
- 最大回撤序列**必须前置起点**，否则第一天就下跌的回撤会被漏算
- 标准差用 `ddof=1`（样本标准差）
- 胜率、盈亏比等交易类指标按**笔**统计，一笔 = 一次完整的买入到卖出

⚠️ **单股回测刻意不报 Sharpe / Sortino / 年化波动率**。
选股策略大部分时间空仓，这些指标会被仓位暴露严重扭曲：只持仓 10% 交易日时，
分子被 90% 的 0 收益稀释到 1/10，分母只降到约 1/3.2，Sharpe 净变为原值的
约 0.32 倍——这与策略好坏无关，纯粹是空仓的副产品。同理不报 Beta。
最大回撤不受影响（空仓期净值走平，定义仍成立），故保留。
"""

import math
from itertools import groupby
from typing import List, Optional

TRADING_DAYS_PER_YEAR = 252
MIN_TRADES_FOR_SIGNIFICANCE = 30


def _safe_div(a: float, b: float) -> Optional[float]:
    return a / b if b else None


def max_drawdown_pct(equity: List[float]) -> float:
    """最大回撤（正数百分比）。前置起点确保首日下跌也被计入。"""
    if not equity:
        return 0.0
    peak = equity[0]
    worst = 0.0
    for value in equity:
        if value > peak:
            peak = value
        if peak > 0:
            dd = (value - peak) / peak
            worst = min(worst, dd)
    return abs(worst) * 100


def max_drawdown_bars(equity: List[float]) -> int:
    """最长回撤持续期（bar 数）：从创新高到重新创新高之间的最大间隔。"""
    if not equity:
        return 0
    peak = equity[0]
    last_peak_idx = 0
    longest = 0
    for i, value in enumerate(equity):
        if value >= peak:
            peak = value
            longest = max(longest, i - last_peak_idx)
            last_peak_idx = i
    longest = max(longest, len(equity) - 1 - last_peak_idx)
    return longest


def max_consecutive_losses(pnls: List[float]) -> int:
    return max((len(list(g)) for k, g in groupby(p < 0 for p in pnls) if k), default=0)


def trade_stats(trades: List) -> dict:
    """交易类指标——稀疏持仓下唯一不被扭曲的一组指标。"""
    n = len(trades)
    if n == 0:
        return {
            'trade_count': 0, 'win_rate': None, 'avg_win': None, 'avg_loss': None,
            'payoff_ratio': None, 'profit_factor': None, 'expectancy': None,
            'best_trade_pct': None, 'worst_trade_pct': None,
            'avg_hold_bars': None, 'max_consecutive_losses': 0, 'sqn': None,
            'total_pnl': 0.0, 'total_cost': 0.0,
        }

    pnls = [t.pnl for t in trades]
    pcts = [t.pnl_pct for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    win_rate = len(wins) / n * 100

    mean_pnl = sum(pnls) / n
    if n > 1:
        var = sum((p - mean_pnl) ** 2 for p in pnls) / (n - 1)
        std = math.sqrt(var)
        # SQN 本质是每笔交易层面的 t 统计量，天然惩罚样本量不足
        sqn = math.sqrt(n) * mean_pnl / std if std else None
    else:
        sqn = None

    return {
        'trade_count': n,
        'win_rate': round(win_rate, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'payoff_ratio': round(avg_win / abs(avg_loss), 2) if avg_loss else None,
        'profit_factor': round(sum(wins) / abs(sum(losses)), 2) if losses else None,
        'expectancy': round(mean_pnl, 2),
        'expectancy_pct': round(sum(pcts) / n, 2),
        'best_trade_pct': round(max(pcts), 2),
        'worst_trade_pct': round(min(pcts), 2),
        'avg_hold_bars': round(sum(t.bars_held for t in trades) / n, 1),
        'max_consecutive_losses': max_consecutive_losses(pnls),
        'sqn': round(sqn, 2) if sqn is not None else None,
        'total_pnl': round(sum(pnls), 2),
        'total_cost': round(sum(t.cost for t in trades), 2),
        'sample_warning': n < MIN_TRADES_FOR_SIGNIFICANCE,
    }


def summarize(result, initial_capital: float) -> dict:
    """单股回测汇总。"""
    equity = [v for _, v in result.equity_curve]
    final = equity[-1] if equity else initial_capital
    total_return = (final - initial_capital) / initial_capital * 100 if initial_capital else 0.0

    n_bars = len(equity)
    # GIPS 硬性要求：不足一年不得年化
    if n_bars >= TRADING_DAYS_PER_YEAR and initial_capital > 0 and final > 0:
        years = n_bars / TRADING_DAYS_PER_YEAR
        annual_return = ((final / initial_capital) ** (1 / years) - 1) * 100
    else:
        annual_return = None

    mdd = max_drawdown_pct(equity)
    exposure = result.exposure_bars / result.total_bars * 100 if result.total_bars else 0.0

    stats = trade_stats(result.trades)
    benchmark = result.benchmark_return_pct

    return {
        'stock_code': result.stock_code,
        'stock_name': result.stock_name,
        'total_return_pct': round(total_return, 2),
        'annual_return_pct': round(annual_return, 2) if annual_return is not None else None,
        'max_drawdown_pct': round(mdd, 2),
        'max_drawdown_bars': max_drawdown_bars(equity),
        'calmar': round(annual_return / mdd, 2) if annual_return and mdd else None,
        'exposure_pct': round(exposure, 2),
        'benchmark_return_pct': round(benchmark, 2) if benchmark is not None else None,
        'excess_return_pct': (
            round((1 + total_return / 100) / (1 + benchmark / 100) * 100 - 100, 2)
            if benchmark is not None and benchmark != -100 else None
        ),
        'final_equity': round(final, 2),
        'bars': n_bars,
        **stats,
    }


def _percentile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    idx = (len(s) - 1) * q
    lo, hi = int(math.floor(idx)), int(math.ceil(idx))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def aggregate(per_stock: List[dict], all_trades: List) -> dict:
    """批量回测聚合。

    刻意**不做**跨股票的 Sharpe / 最大回撤平均——各股回撤不同时发生，
    平均值对应不到任何可执行的组合，无可解释含义。
    改为两个都成立的口径：
      1. 交易池合并 → 池级别的信号质量指标
      2. 截面分布 → 中位数与分位数（A 股个股收益右偏厚尾，只报均值会严重误导）
    """
    if not per_stock:
        return {'stock_count': 0, 'pool': trade_stats([]), 'cross_section': {}}

    returns = [s['total_return_pct'] for s in per_stock]
    excess = [s['excess_return_pct'] for s in per_stock if s['excess_return_pct'] is not None]
    positive = [r for r in returns if r > 0]

    best = max(per_stock, key=lambda s: s['total_return_pct'])
    worst = min(per_stock, key=lambda s: s['total_return_pct'])

    return {
        'stock_count': len(per_stock),
        # 交易池：把所有股票的交易合并成一个池，衡量信号质量
        'pool': trade_stats(all_trades),
        # 截面分布：均值必须与中位数并列
        'cross_section': {
            'mean_return_pct': round(sum(returns) / len(returns), 2),
            'median_return_pct': round(_percentile(returns, 0.5), 2),
            'p25_return_pct': round(_percentile(returns, 0.25), 2),
            'p75_return_pct': round(_percentile(returns, 0.75), 2),
            'positive_ratio': round(len(positive) / len(returns) * 100, 2),
            'mean_excess_pct': round(sum(excess) / len(excess), 2) if excess else None,
            'best': {'code': best['stock_code'], 'name': best['stock_name'],
                     'return_pct': best['total_return_pct']},
            'worst': {'code': worst['stock_code'], 'name': worst['stock_name'],
                      'return_pct': worst['total_return_pct']},
        },
    }
