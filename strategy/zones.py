"""
strategy/zones.py — demand/supply zone detection and broken-level lookup.
"""
import numpy as np
from config import MIN_ZONE_CANDLES, ZONE_LOOKBACK


def detect_zones(df):
    df = df.copy()
    df['demand_zone_top']    = np.nan
    df['demand_zone_bottom'] = np.nan
    df['supply_zone_top']    = np.nan
    df['supply_zone_bottom'] = np.nan
    closes, opens = df['Close'].values, df['Open'].values
    highs, lows   = df['High'].values, df['Low'].values
    for i in range(MIN_ZONE_CANDLES, len(df)):
        bull = all(closes[i-j] > opens[i-j] for j in range(MIN_ZONE_CANDLES))
        bear = all(closes[i-j] < opens[i-j] for j in range(MIN_ZONE_CANDLES))
        z = i - MIN_ZONE_CANDLES
        if bull and z >= 0:
            df.iloc[i, df.columns.get_loc('demand_zone_top')]    = highs[z]
            df.iloc[i, df.columns.get_loc('demand_zone_bottom')] = lows[z]
        if bear and z >= 0:
            df.iloc[i, df.columns.get_loc('supply_zone_top')]    = highs[z]
            df.iloc[i, df.columns.get_loc('supply_zone_bottom')] = lows[z]
    return df


def get_broken_level(df, i, direction, lookback=ZONE_LOOKBACK):
    close = float(df['Close'].iloc[i])
    lb = min(i, lookback)
    if direction == 1:
        sh = df['High'].iloc[i-lb:i][df['swing_high'].iloc[i-lb:i]]
        b = sh[sh < close]
        return float(b.iloc[-1]) if not b.empty else None
    else:
        sl = df['Low'].iloc[i-lb:i][df['swing_low'].iloc[i-lb:i]]
        b = sl[sl > close]
        return float(b.iloc[-1]) if not b.empty else None
