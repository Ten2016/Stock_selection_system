"""回测编排层：取数 → 生成买点 → 逐股回测 → 聚合。

买入条件直接复用选股策略（`services/strategies/`）——选股和买点本来就是
同一个判断的两种用法：选股是在最后一根 bar 上判一次，回测是逐 bar 重放。
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.stock import StockBasic
from app.models.stock_kline import StockKline
from . import strategies
from .backtest import (
    BacktestConfig, ExitGroup, TradeCost, aggregate, all_exit_rules,
    get_exit_rule, run_backtest, summarize,
)
from .strategies.common import STRATEGY_COLUMNS

# 指标预热：MACD 是 EMA 递归，前 ~100 根不稳定；MA60 也需要 60 根。
# 统一取 120，避免数据开头产生假信号。
WARMUP_BARS = 120

MAX_BACKTEST_STOCKS = 100


def get_entry_rules() -> List[dict]:
    """可用买入条件 = 全部选股策略。"""
    return [s.meta.to_dict() for s in strategies.all_strategies()]


def get_exit_rules() -> List[dict]:
    return [r.meta.to_dict() for r in all_exit_rules()]


def _load_bars(db: Session, code: str, start: Optional[date], end: Optional[date]) -> List:
    query = db.query(*STRATEGY_COLUMNS).filter(StockKline.stock_code == code)
    if start is not None:
        query = query.filter(StockKline.trade_date >= start)
    if end is not None:
        query = query.filter(StockKline.trade_date <= end)
    return query.order_by(StockKline.trade_date.asc()).all()


def _resolve_exit_groups(specs: List[dict]) -> List[ExitGroup]:
    """把前端传来的条件组解析成引擎结构。

    入参形如 `[{logic: 'any'|'all', rules: [{name, params}]}]`。
    组间恒为 OR，组内按 logic 合并——这是析取范式，可表达任意布尔组合。
    组按「组内最高优先级」排序：风控类（止损）无条件优先于收益类和时间类。
    """
    groups: List[ExitGroup] = []
    for spec in specs:
        rules: List[Tuple[Any, dict]] = []
        for item in spec.get('rules') or []:
            rule = get_exit_rule(item.get('name', ''))
            if rule is None:
                continue
            rules.append((rule, rule.coerce_params(item.get('params') or {})))
        if not rules:
            continue
        logic = 'all' if spec.get('logic') == 'all' else 'any'
        rules.sort(key=lambda pair: pair[0].meta.priority)
        groups.append(ExitGroup(logic=logic, rules=rules))

    groups.sort(key=lambda g: min(r.meta.priority for r, _ in g.rules))
    return groups


def _build_config(raw: Optional[dict]) -> BacktestConfig:
    raw = raw or {}
    cost = TradeCost(
        commission_rate=float(raw.get('commission_rate', 0.00025)),
        min_commission=float(raw.get('min_commission', 5.0)),
        stamp_tax_rate=float(raw.get('stamp_tax_rate', 0.0005)),
        transfer_fee_rate=float(raw.get('transfer_fee_rate', 0.00001)),
        slippage_rate=float(raw.get('slippage_rate', 0.001)),
    )
    return BacktestConfig(
        initial_capital=float(raw.get('initial_capital', 100_000)),
        execution=raw.get('execution', 'next_open'),
        exit_timing=raw.get('exit_timing', 'same_day'),
        check_price_limit=bool(raw.get('check_price_limit', True)),
        cost=cost,
    )


def run(
    db: Session,
    stock_codes: List[str],
    entry_name: str,
    entry_params: Optional[dict] = None,
    exit_groups: Optional[List[dict]] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    config_raw: Optional[dict] = None,
) -> dict:
    """对一批股票各自独立满仓回测，再横向聚合。"""
    entry = strategies.get_strategy(entry_name)
    if entry is None:
        return {'error': f'未知的买入条件：{entry_name}'}

    groups = _resolve_exit_groups(exit_groups or [])
    if not groups:
        return {'error': '至少需要选择一个卖出规则'}

    entry_params = entry.coerce_params(entry_params or {})
    config = _build_config(config_raw)
    codes = stock_codes[:MAX_BACKTEST_STOCKS]

    names = {
        s.code: s.name
        for s in db.query(StockBasic.code, StockBasic.name)
                   .filter(StockBasic.code.in_(codes)).all()
    }

    per_stock: List[dict] = []
    all_trades: List = []
    details: Dict[str, dict] = {}
    skipped: List[dict] = []

    for code in codes:
        bars = _load_bars(db, code, start_date, end_date)
        if len(bars) < WARMUP_BARS + 20:
            skipped.append({'code': code, 'name': names.get(code, ''),
                            'reason': f'K线不足（{len(bars)} 根，至少需 {WARMUP_BARS + 20} 根）'})
            continue

        # 买点由策略自己的 find_signals 产出，其内部已保证无未来函数
        try:
            signals = entry.find_signals(bars, start_year=1900, **entry_params)
        except Exception as exc:
            skipped.append({'code': code, 'name': names.get(code, ''), 'reason': f'买入条件计算失败：{exc}'})
            continue

        signal_dates = {s['date'] for s in signals}

        result = run_backtest(
            stock_code=code, stock_name=names.get(code, ''), bars=bars,
            entry_signal_dates=signal_dates, exit_groups=groups,
            config=config, warmup=WARMUP_BARS,
        )

        stats = summarize(result, config.initial_capital)
        per_stock.append(stats)
        all_trades.extend(result.trades)
        details[code] = {
            'trades': [t.to_dict() for t in result.trades],
            'equity_curve': [
                {'date': d.isoformat(), 'equity': round(v, 2)}
                for d, v in result.equity_curve
            ],
        }

    per_stock.sort(key=lambda s: s['total_return_pct'], reverse=True)

    return {
        'entry': {'name': entry.meta.name, 'display_name': entry.meta.display_name,
                  'params': entry_params},
        'exit_groups': [
            {'logic': g.logic,
             'rules': [{'name': r.meta.name, 'display_name': r.meta.display_name, 'params': p}
                       for r, p in g.rules]}
            for g in groups
        ],
        'config': {
            'initial_capital': config.initial_capital,
            'execution': config.execution,
            'exit_timing': config.exit_timing,
            'commission_rate': config.cost.commission_rate,
            'min_commission': config.cost.min_commission,
            'stamp_tax_rate': config.cost.stamp_tax_rate,
            'slippage_rate': config.cost.slippage_rate,
        },
        'per_stock': per_stock,
        'summary': aggregate(per_stock, all_trades),
        'details': details,
        'skipped': skipped,
    }
