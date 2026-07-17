"""
strategy/indicators.py — EMA trend, ATR, swing high/low detection.
"""
import pandas as pd
import numpy as np
from config import EMA_PERIOD, ATR_PERIOD, SWING_LOOKBACK


def calculate_indicators(df):
    df = df.copy()
    df['ema100'] = df['Close'].ewm(span=EMA_PERIOD, adjust=False).mean()
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift()).abs()
    lc = (df['Low']  - df['Close'].shift()).abs()
    df['atr'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).ewm(span=ATR_PERIOD, adjust=False).mean()
    df['trend'] = np.where(df['Close'] > df['ema100'], 1, -1)
    df['swing_high'] = False
    df['swing_low']  = False
    n = SWING_LOOKBACK
    for i in range(n, len(df) - n):
        if df['High'].iloc[i] == df['High'].iloc[i-n:i+n+1].max():
            df.iloc[i, df.columns.get_loc('swing_high')] = True
        if df['Low'].iloc[i] == df['Low'].iloc[i-n:i+n+1].min():
            df.iloc[i, df.columns.get_loc('swing_low')] = True
    return df
