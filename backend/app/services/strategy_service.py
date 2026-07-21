"""策略编排层：只负责取数据、遍历、调度，不含任何策略逻辑。

策略本身全部在 `app/services/strategies/` 下，由注册表自动发现。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.stock import StockBasic
from . import strategies
from .strategies.common import CHUNK_SIZE, get_sorted_klines, load_klines_bulk

# 回测取更长的历史窗口
BACKTEST_MAX_DAYS = 1500


def get_available_strategies() -> List[dict]:
    return [s.meta.to_dict() for s in strategies.all_strategies()]


def coerce_params(strategy_name: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """按策略自身的参数声明解析外部传入的参数；未知策略返回空字典。"""
    strategy = strategies.get_strategy(strategy_name)
    return strategy.coerce_params(raw) if strategy else {}


def run_strategy(
    db: Session,
    strategy_name: str,
    min_market_cap: Optional[float] = None,
    params: Optional[Dict[str, Any]] = None,
) -> List[dict]:
    strategy = strategies.get_strategy(strategy_name)
    if strategy is None:
        return []

    params = params or strategy.defaults()

    query = db.query(StockBasic)
    if min_market_cap is not None:
        # total_cap 单位为亿元（见 sync_service.fetch_all_stocks_basic_info），与入参同单位
        query = query.filter(StockBasic.total_cap >= min_market_cap)
    stocks = query.all()

    results = []
    # 分批批量加载 K 线，避免逐股查询（N+1），同时限制单批内存占用
    for offset in range(0, len(stocks), CHUNK_SIZE):
        batch = stocks[offset:offset + CHUNK_SIZE]
        klines_map = load_klines_bulk(db, [s.code for s in batch])

        for stock in batch:
            klines = klines_map.get(stock.code)
            if klines is None:
                # 批量窗口内无数据（如长期停牌），回落到单股查询
                klines = get_sorted_klines(stock.code, db)
            if len(klines) < strategy.min_klines:
                continue

            try:
                result = strategy.check(klines, **params)
            except Exception:
                continue

            if result:
                results.append({
                    'code': stock.code,
                    'name': stock.name,
                    'total_cap': stock.total_cap,
                    'result': result,
                })

    return results


def backtest_strategy(
    db: Session,
    stock_code: str,
    strategy_name: str,
    start_year: int = 2020,
    params: Optional[Dict[str, Any]] = None,
) -> dict:
    stock = db.query(StockBasic).filter(StockBasic.code == stock_code).first()
    strategy = strategies.get_strategy(strategy_name)

    empty = {
        'stock_code': stock_code,
        'stock_name': stock.name if stock else '',
        'total_cap': float(stock.total_cap) if stock and stock.total_cap is not None else None,
        'signals': [],
        'signal_count': 0,
    }
    if stock is None or strategy is None:
        return empty

    klines = get_sorted_klines(stock_code, db, max_days=BACKTEST_MAX_DAYS)
    if len(klines) < 120:
        return empty

    params = params or strategy.defaults()
    signals = strategy.find_signals(klines, start_year, **params)

    return {**empty, 'signals': signals, 'signal_count': len(signals)}
