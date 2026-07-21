import pandas as pd
from typing import Tuple


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    return prices.ewm(span=period, adjust=False).mean()


def calculate_macd(
    closes: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = calculate_ema(closes, fast)
    ema_slow = calculate_ema(closes, slow)
    dif = ema_fast - ema_slow
    dea = calculate_ema(dif, signal)
    macd_hist = 2 * (dif - dea)
    return dif, dea, macd_hist


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df['MA5'] = df['close'].rolling(window=5).mean().round(2)
    df['MA10'] = df['close'].rolling(window=10).mean().round(2)
    df['MA20'] = df['close'].rolling(window=20).mean().round(2)
    df['MA30'] = df['close'].rolling(window=30).mean().round(2)
    df['MA60'] = df['close'].rolling(window=60).mean().round(2)
    
    std = df['close'].rolling(window=20).std()
    df['boll_upper'] = (df['MA20'] + 2 * std).round(2)
    df['boll_mid'] = df['MA20']
    df['boll_lower'] = (df['MA20'] - 2 * std).round(2)
    
    dif, dea, macd_hist = calculate_macd(df['close'])
    df['dif'] = dif.round(4)
    df['dea'] = dea.round(4)
    df['macd'] = macd_hist.round(4)
    
    return df
