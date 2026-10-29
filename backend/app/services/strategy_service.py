"""策略编排层：只负责取数据、遍历、调度，不含任何策略逻辑。

策略本身全部在 `app/services/strategies/` 下，由注册表自动发现。
"""

from typing import Any, Dict, List, Optional
import logging

from sqlalchemy.orm import Session

from app.models.stock import StockBasic
from . import strategies
from .strategies.common import CHUNK_SIZE, get_sorted_klines, load_klines_bulk

logger = logging.getLogger(__name__)


def get_available_strategies() -> List[dict]:
    return [s.meta.to_dict() for s in strategies.all_strategies()]


def coerce_params(strategy_name: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """按策略自身的参数声明解析外部传入的参数。"""
    strategy = strategies.get_strategy(strategy_name)
    if strategy is None:
        raise ValueError(f'未知的策略：{strategy_name}')
    return strategy.coerce_params(raw)


def run_strategy(
    db: Session,
    strategy_name: str,
    min_market_cap: Optional[float] = None,
    params: Optional[Dict[str, Any]] = None,
) -> List[dict]:
    strategy = strategies.get_strategy(strategy_name)
    if strategy is None:
        raise ValueError(f'未知的策略：{strategy_name}')

    params = params or strategy.defaults()

    max_days = max(200, strategy.required_klines(**params))
    query = db.query(StockBasic).filter(StockBasic.is_active.is_(True))
    if min_market_cap is not None:
        # total_cap 单位为亿元（见 sync_service.fetch_all_stocks_basic_info），与入参同单位
        query = query.filter(StockBasic.total_cap >= min_market_cap)
    stocks = query.all()

    results = []
    # 分批批量加载 K 线，避免逐股查询（N+1），同时限制单批内存占用
    for offset in range(0, len(stocks), CHUNK_SIZE):
        batch = stocks[offset:offset + CHUNK_SIZE]
        klines_map = load_klines_bulk(db, [s.code for s in batch], max_days=max_days)

        for stock in batch:
            klines = klines_map.get(stock.code)
            if klines is None or len(klines) < max_days:
                # 自然日窗口可能受停牌影响，不足时按实际交易日补取
                klines = get_sorted_klines(stock.code, db, max_days=max_days)
            if len(klines) < strategy.required_klines(**params):
                continue

            try:
                result = strategy.check(klines, **params)
            except Exception as exc:
                logger.exception('策略 %s 计算股票 %s 失败', strategy_name, stock.code)
                raise ValueError(f'股票 {stock.code} 策略计算失败') from exc

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
    if stock is None:
        raise ValueError(f'股票不存在：{stock_code}')
    if strategy is None:
        raise ValueError(f'未知的策略：{strategy_name}')

    klines = get_sorted_klines(stock_code, db, max_days=None)
    if len(klines) < 120:
        return empty

    params = params or strategy.defaults()
    try:
        signals = strategy.find_signals(klines, start_year, **params)
    except Exception as exc:
        logger.exception('策略 %s 计算股票 %s 历史信号失败', strategy_name, stock_code)
        raise ValueError(f'股票 {stock_code} 历史信号计算失败') from exc

    return {**empty, 'signals': signals, 'signal_count': len(signals)}
