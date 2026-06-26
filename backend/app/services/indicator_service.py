import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple


def calculate_ma(prices: List[float], window: int) -> List[Optional[float]]:
    s = pd.Series(prices)
    ma = s.rolling(window=window).mean()
    return ma.round(2).tolist()


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


def calculate_bollinger_bands(
    closes: List[float],
    ma_values: List[Optional[float]],
    period: int = 20,
    std_dev_multiplier: int = 2
):
    s = pd.Series(closes)
    std = s.rolling(window=period).std()
    upper = []
    lower = []
    for i in range(len(closes)):
        ma = ma_values[i] if i < len(ma_values) else None
        std_val = std.iloc[i] if i < len(std) else None
        if ma is not None and std_val is not None and not pd.isna(std_val):
            upper.append(round(float(ma + std_dev_multiplier * std_val), 2))
            lower.append(round(float(ma - std_dev_multiplier * std_val), 2))
        else:
            upper.append(None)
            lower.append(None)
    return upper, lower


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
