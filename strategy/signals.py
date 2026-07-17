"""
strategy/signals.py — signal detection (trend strength + zone/level checks),
alert cooldown, and candle-freshness tracking.
"""
import pandas as pd
from datetime import datetime, timezone
from config import ALLOWED_TREND_STRENGTHS, NEAR_LEVEL_ATR_MULT, SL_BUFFER_ATR_MULT, \
    RR_RATIO, SWING_LOOKBACK, MIN_ZONE_CANDLES, MIN_SIGNAL_GAP_HOURS
from strategy.zones import get_broken_level
from storage import last_processed_candle, last_signal, save_signal_state


def check_for_signal(df):
    n = len(df)
    if n < SWING_LOOKBACK + MIN_ZONE_CANDLES + 5:
        return None, "not enough candles yet"
    i = n - 1
    row = df.iloc[i]
    close = float(row['Close'])
    trend = int(row['trend'])
    atr   = float(row['atr']) if not pd.isna(row['atr']) else 0
    if atr <= 0:
        return None, "ATR is zero/invalid"

    ema  = float(row['ema100'])
    dist = abs(close - ema)
    trend_str = "Strong" if dist > (3*atr) else "Moderate" if dist > atr else "Weak"
    if trend_str not in ALLOWED_TREND_STRENGTHS:
        return None, f"trend is {trend_str}, not allowed"

    direction = trend
    broken = get_broken_level(df, i, direction)
    if broken is None:
        return None, f"{trend_str} trend but no broken swing level found"

    zone_top = zone_bot = None
    for j in range(i, max(i-50, 0), -1):
        if direction == 1 and not pd.isna(df['demand_zone_top'].iloc[j]):
            zone_top = float(df['demand_zone_top'].iloc[j]); zone_bot = float(df['demand_zone_bottom'].iloc[j]); break
        elif direction == -1 and not pd.isna(df['supply_zone_top'].iloc[j]):
            zone_top = float(df['supply_zone_top'].iloc[j]); zone_bot = float(df['supply_zone_bottom'].iloc[j]); break
    if zone_top is None:
        return None, f"{trend_str} trend + broken level, but no demand/supply zone found nearby"

    near_tol = NEAR_LEVEL_ATR_MULT * atr
    sl_buf   = SL_BUFFER_ATR_MULT * atr
    in_zone  = zone_bot <= close <= zone_top
    dist_to_level = abs(close - broken)
    if not (dist_to_level <= near_tol or in_zone):
        return None, (f"zone exists but price is {dist_to_level:.2f} away from level "
                       f"(tolerance is {near_tol:.2f}) and not inside the zone")

    if direction == 1:
        entry = zone_top + sl_buf
        sl    = zone_bot - sl_buf
        sl_dist = entry - sl
        tp    = entry + sl_dist * RR_RATIO
    else:
        entry = zone_bot - sl_buf
        sl    = zone_top + sl_buf
        sl_dist = sl - entry
        tp    = entry - sl_dist * RR_RATIO

    if sl_dist < atr * 0.3:
        return None, "stop distance too tight relative to ATR — rejected"

    return {'direction': 'BUY' if direction == 1 else 'SELL', 'entry': entry, 'sl': sl,
            'tp': tp, 'zone_top': zone_top, 'zone_bot': zone_bot, 'trend': trend_str}, "signal fired"


# ── Candle-freshness tracking (per symbol+interval) ──

def is_new_candle(symbol, interval, df):
    key = f"{symbol}_{interval}"
    latest_ts = df.index[-1]
    if last_processed_candle.get(key) == latest_ts:
        return False
    return True

def mark_candle_processed(symbol, interval, df):
    key = f"{symbol}_{interval}"
    last_processed_candle[key] = df.index[-1]
    save_signal_state()

# ── Alert cooldown (per symbol+direction) ──

def already_alerted(symbol, direction):
    key = f"{symbol}_{direction}"
    if key not in last_signal:
        return False
    return (datetime.now(timezone.utc) - last_signal[key]).total_seconds() / 3600 < MIN_SIGNAL_GAP_HOURS

def mark_alerted(symbol, direction):
    last_signal[f"{symbol}_{direction}"] = datetime.now(timezone.utc)
    save_signal_state()
