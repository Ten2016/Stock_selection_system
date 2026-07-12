from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.stock import StockBasic
from app.models.stock_kline import StockKline
from .strategies.common import get_sorted_klines
from .strategies.consecutive_ma5 import check_consecutive_ma5
from .strategies.rise_then_fall import check_rise_then_fall
from .strategies.above_ma60 import check_above_ma60
from .strategies.macd_green_pullback import check_macd_green_pullback, _find_green_waves


STRATEGY_LIST = [
    {
        'name': 'consecutive_ma5',
        'label': '跌破布林下轨后连续站MA5',
        'description': '往前x天内跌破布林下轨，之后y天内连续z天站上5日均线',
        'params': ['x_days', 'y_days', 'z_days']
    },
    {
        'name': 'rise_then_fall',
        'label': '大涨后连续下跌',
        'description': '往前x天内涨幅大于y%，之后连续z天都是下跌',
        'params': ['x_days', 'y_pct', 'z_days']
    },
    {
        'name': 'above_ma60',
        'label': '站上60日均线',
        'description': '最近y天内有z天站上60日均线',
        'params': ['y_days', 'z_days']
    },
    {
        'name': 'macd_green_pullback',
        'label': 'MACD绿柱拐点上升通道',
        'description': '绿柱拐点后缩短确认，股价一底比一底高',
        'params': ['y_days', 'confirm_days', 'min_wave_days', 'tolerate_red']
    }
]


def get_available_strategies() -> List[dict]:
    return STRATEGY_LIST


def run_strategy_for_stock(
    db: Session,
    stock: StockBasic,
    strategy_name: str,
    x_days: int = 30,
    y_days: int = 10,
    z_days: int = 2,
    y_pct: float = 5.0,
    confirm_days: int = 2,
    min_wave_days: int = 3,
    tolerate_red: int = 1
) -> Optional[dict]:
    klines = get_sorted_klines(stock.code, db)

    if len(klines) < 20:
        return None

    result = None

    if strategy_name == 'consecutive_ma5':
        result = check_consecutive_ma5(klines, x_days, y_days, z_days)
    elif strategy_name == 'rise_then_fall':
        result = check_rise_then_fall(klines, x_days, y_pct, z_days)
    elif strategy_name == 'above_ma60':
        result = check_above_ma60(klines, y_days, z_days)
    elif strategy_name == 'macd_green_pullback':
        result = check_macd_green_pullback(klines, y_days, confirm_days, min_wave_days, tolerate_red)

    if result:
        return {
            'code': stock.code,
            'name': stock.name,
            'total_cap': stock.total_cap,
            'result': result
        }

    return None


def run_strategy(
    db: Session,
    strategy_name: str,
    min_market_cap: Optional[float] = None,
    x_days: int = 30,
    y_days: int = 10,
    z_days: int = 2,
    y_pct: float = 5.0,
    confirm_days: int = 2,
    min_wave_days: int = 3,
    tolerate_red: int = 1
) -> List[dict]:
    query = db.query(StockBasic)

    if min_market_cap is not None:
        query = query.filter(StockBasic.total_cap >= min_market_cap * 100000000)

    stocks = query.all()

    results = []
    for stock in stocks:
        try:
            result = run_strategy_for_stock(
                db, stock, strategy_name,
                x_days=x_days,
                y_days=y_days,
                z_days=z_days,
                y_pct=y_pct,
                confirm_days=confirm_days,
                min_wave_days=min_wave_days,
                tolerate_red=tolerate_red
            )
            if result:
                results.append(result)
        except Exception:
            continue

    return results


def backtest_strategy(
    db: Session,
    stock_code: str,
    strategy_name: str,
    start_year: int = 2020,
    x_days: int = 30,
    y_days: int = 10,
    z_days: int = 2,
    y_pct: float = 5.0,
    confirm_days: int = 2,
    min_wave_days: int = 3,
    tolerate_red: int = 1
) -> dict:
    stock = db.query(StockBasic).filter(StockBasic.code == stock_code).first()

    if not stock:
        return {'stock_code': stock_code, 'stock_name': '', 'signals': []}

    klines = get_sorted_klines(stock_code, db, max_days=1500)

    if len(klines) < 120:
        return {'stock_code': stock_code, 'stock_name': stock.name, 'signals': []}

    start_idx = next((i for i, bar in enumerate(klines) if bar.trade_date.year >= start_year), 0)

    signals = []
    prev_signal_date = None

    if strategy_name == 'macd_green_pullback':
        waves = _find_green_waves(klines, min_days=min_wave_days, tolerate_red=tolerate_red)

        for wave_idx, wave in enumerate(waves):
            if wave_idx == 0:
                continue

            prev_wave = waves[wave_idx - 1]
            valley_idx = wave['valley_idx']

            if klines[valley_idx].trade_date.year < start_year:
                continue

            if wave['min_low'] is None or prev_wave['min_low'] is None:
                continue

            if wave['min_low'] <= prev_wave['min_low']:
                continue

            for j in range(valley_idx + confirm_days, min(valley_idx + y_days + 1, len(klines))):
                if klines[j].macd is None or klines[j - 1].macd is None:
                    continue

                is_shortening = True
                for k in range(valley_idx + 1, j + 1):
                    if klines[k].macd is None or klines[k - 1].macd is None:
                        is_shortening = False
                        break
                    if klines[k].macd < klines[k - 1].macd:
                        is_shortening = False
                        break

                if is_shortening:
                    bar = klines[j]
                    valley_date = klines[valley_idx].trade_date.strftime('%Y-%m-%d')
                    curr_date = bar.trade_date.strftime('%Y-%m-%d')

                    strategy_name_str = (f'MACD绿柱拐点上升通道：最近{y_days}天内出现绿柱拐点，'
                                        f'缩短{confirm_days}天确认，股价一底比一底高')

                    low_diff_pct = None
                    if wave['min_low'] and prev_wave['min_low']:
                        low_diff_pct = round(
                            (float(wave['min_low']) - float(prev_wave['min_low'])) / float(prev_wave['min_low']) * 100, 2
                        )

                    signals.append({
                        'date': curr_date,
                        'close': float(bar.close) if bar.close else None,
                        'strategy': strategy_name_str,
                        'valley_date': valley_date,
                        'valley_macd': float(wave['valley_macd']) if wave['valley_macd'] is not None else None,
                        'shortening_days': j - valley_idx,
                        'current_min_low': float(wave['min_low']),
                        'current_min_low_date': wave['min_low_date'].strftime('%Y-%m-%d'),
                        'prev_min_low': float(prev_wave['min_low']),
                        'prev_min_low_date': prev_wave['min_low_date'].strftime('%Y-%m-%d'),
                        'low_diff_pct': low_diff_pct,
                        'details': {}
                    })
                    break
    else:
        check_func = None
        if strategy_name == 'consecutive_ma5':
            check_func = lambda data: check_consecutive_ma5(data, x_days, y_days, z_days)
        elif strategy_name == 'rise_then_fall':
            check_func = lambda data: check_rise_then_fall(data, x_days, y_pct, z_days)
        elif strategy_name == 'above_ma60':
            check_func = lambda data: check_above_ma60(data, y_days, z_days)

        if check_func:
            for i in range(start_idx, len(klines)):
                data_slice = klines[:i + 1]
                result = check_func(data_slice)

                if result:
                    signal_date = klines[i].trade_date.strftime('%Y-%m-%d')

                    if signal_date != prev_signal_date:
                        prev_signal_date = signal_date
                        signals.append({
                            'date': signal_date,
                            'close': float(klines[i].close) if klines[i].close else None,
                            **result
                        })

    return {
        'stock_code': stock_code,
        'stock_name': stock.name,
        'total_cap': float(stock.total_cap) if stock.total_cap else None,
        'signals': signals,
        'signal_count': len(signals)
    }
