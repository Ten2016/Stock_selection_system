from typing import List, Optional

from app.models.stock_kline import StockKline


def _find_green_waves(klines: List[StockKline], min_days: int = 3, tolerate_red: int = 1) -> List[dict]:
    waves = []
    n = len(klines)
    i = 0

    while i < n:
        if klines[i].macd is not None and klines[i].macd < 0:
            start_idx = i
            end_idx = i
            valley_idx = i
            valley_macd = klines[i].macd
            min_low = klines[i].low
            min_low_date = klines[i].trade_date

            red_streak = 0
            j = i + 1

            while j < n:
                bar = klines[j]

                if bar.macd is not None and bar.macd < 0:
                    red_streak = 0
                    end_idx = j
                    if bar.macd < valley_macd:
                        valley_idx = j
                        valley_macd = bar.macd
                    if bar.low is not None and (min_low is None or bar.low < min_low):
                        min_low = bar.low
                        min_low_date = bar.trade_date

                    j += 1
                else:
                    red_streak += 1
                    if red_streak > tolerate_red:
                        break
                    j += 1

            if end_idx - start_idx + 1 >= min_days:
                waves.append({
                    'start_idx': start_idx,
                    'end_idx': end_idx,
                    'valley_idx': valley_idx,
                    'valley_macd': valley_macd,
                    'min_low': min_low,
                    'min_low_date': min_low_date
                })

            i = j
        else:
            i += 1

    return waves


def check_macd_green_pullback(
    klines: List[StockKline],
    y_days: int = 5,
    confirm_days: int = 2,
    min_wave_days: int = 3,
    tolerate_red: int = 1
) -> Optional[dict]:
    if len(klines) < 60:
        return None

    waves = _find_green_waves(klines, min_days=min_wave_days, tolerate_red=tolerate_red)

    if len(waves) < 2:
        return None

    current_wave = waves[-1]
    prev_wave = waves[-2]

    latest_idx = len(klines) - 1
    valley_idx = current_wave['valley_idx']

    if latest_idx - valley_idx < confirm_days:
        return None

    if latest_idx - valley_idx > y_days:
        return None

    shortening = True
    for k in range(valley_idx + 1, latest_idx + 1):
        if klines[k].macd is None or klines[k - 1].macd is None:
            shortening = False
            break
        if klines[k].macd < klines[k - 1].macd:
            shortening = False
            break

    if not shortening:
        return None

    if current_wave['min_low'] is None or prev_wave['min_low'] is None:
        return None

    if current_wave['min_low'] <= prev_wave['min_low']:
        return None

    valley_date = klines[valley_idx].trade_date.strftime('%Y-%m-%d')
    valley_macd_val = float(current_wave['valley_macd']) if current_wave['valley_macd'] is not None else None

    strategy_name = (f'MACD绿柱拐点上升通道：最近{y_days}天内出现绿柱拐点，'
                     f'缩短{confirm_days}天确认，股价一底比一底高')

    low_diff_pct = None
    if current_wave['min_low'] and prev_wave['min_low']:
        low_diff_pct = round(
            (float(current_wave['min_low']) - float(prev_wave['min_low'])) / float(prev_wave['min_low']) * 100, 2
        )

    return {
        'strategy': strategy_name,
        'valley_date': valley_date,
        'valley_macd': valley_macd_val,
        'shortening_days': latest_idx - valley_idx,
        'current_min_low': float(current_wave['min_low']),
        'current_min_low_date': current_wave['min_low_date'].strftime('%Y-%m-%d'),
        'prev_min_low': float(prev_wave['min_low']),
        'prev_min_low_date': prev_wave['min_low_date'].strftime('%Y-%m-%d'),
        'low_diff_pct': low_diff_pct,
        'details': {}
    }
