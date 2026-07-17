"""BTCUSDT 5-minute-entry backtest with the live bot's two-stage exit.

This is deliberately separate from the Telegram bot: it uses only historical
Binance candles and never imports credentials, state, or notification code.

The default model is conservative when OHLC cannot reveal intrabar order:
an already-active stop wins any same-bar collision.  This makes results a
useful lower-bound, not a claim of tick-level execution accuracy.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

import numpy as np
import pandas as pd
import requests


URL = "https://api.binance.com/api/v3/klines"
CACHE_DIR = Path(".backtest_cache")
EMA, ATR, RR = 100, 14, 2.0
MIN_ZONE, SWING, ZONE_LOOKBACK = 4, 12, 100
NEAR, SL_BUFFER, COOLDOWN = .5, .2, 4
TP1_FRACTION, TP1_CLOSE, TRAIL = .5, .5, 1.0


def fetch(symbol, interval, days, end_days_ago=0):
    CACHE_DIR.mkdir(exist_ok=True)
    cache = CACHE_DIR / f"{symbol}_{interval}_{days}d_{end_days_ago}ago.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    end = int(time.time() * 1000) - end_days_ago * 86_400_000
    start, rows = end - days * 86_400_000, []
    interval_ms = {"1h": 3_600_000, "5m": 300_000}[interval]
    starts = range(start, end, interval_ms * 1000)

    def request_chunk(cursor):
        params = {"symbol": symbol, "interval": interval, "startTime": cursor,
                  "endTime": min(end, cursor + interval_ms * 1000 - 1), "limit": 1000}
        for attempt in range(3):
            try:
                response = requests.get(URL, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(1 << attempt)

    # Binance caps each response at 1,000 candles. Eight requests stay well
    # under its public request-weight budget while making yearly 5M tests viable.
    with ThreadPoolExecutor(max_workers=8) as pool:
        for chunk in pool.map(request_chunk, starts):
            rows.extend(chunk)
    if not rows:
        raise RuntimeError("Binance returned no candles")
    df = pd.DataFrame(rows, columns=["open_time", "Open", "High", "Low", "Close", "volume",
                                     "close_time", "quote_volume", "trades", "taker_base",
                                     "taker_quote", "ignore"])
    df["datetime"] = pd.to_datetime(df.pop("open_time"), unit="ms")
    for col in ("Open", "High", "Low", "Close"):
        df[col] = df[col].astype(float)
    result = df.set_index("datetime")[["Open", "High", "Low", "Close"]].sort_index()
    result.to_pickle(cache)
    return result


def enrich(df, swing):
    df = df.copy()
    df["ema"] = df.Close.ewm(span=EMA, adjust=False).mean()
    tr = pd.concat([df.High - df.Low, (df.High - df.Close.shift()).abs(),
                    (df.Low - df.Close.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(span=ATR, adjust=False).mean()
    df["trend"] = np.where(df.Close > df.ema, 1, -1)
    df["swing_high"] = False
    df["swing_low"] = False
    for i in range(swing, len(df) - swing):
        df.iloc[i, df.columns.get_loc("swing_high")] = df.High.iloc[i] == df.High.iloc[i-swing:i+swing+1].max()
        df.iloc[i, df.columns.get_loc("swing_low")] = df.Low.iloc[i] == df.Low.iloc[i-swing:i+swing+1].min()
    return df


def zones(df, minimum):
    df = df.copy()
    for col in ("demand_top", "demand_bottom", "supply_top", "supply_bottom"):
        df[col] = np.nan
    for i in range(minimum, len(df)):
        bullish = all(df.Close.iloc[i-j] > df.Open.iloc[i-j] for j in range(minimum))
        bearish = all(df.Close.iloc[i-j] < df.Open.iloc[i-j] for j in range(minimum))
        z = i - minimum
        if bullish:
            df.iloc[i, df.columns.get_loc("demand_top")] = df.High.iloc[z]
            df.iloc[i, df.columns.get_loc("demand_bottom")] = df.Low.iloc[z]
        if bearish:
            df.iloc[i, df.columns.get_loc("supply_top")] = df.High.iloc[z]
            df.iloc[i, df.columns.get_loc("supply_bottom")] = df.Low.iloc[z]
    return df


def signal(df, i, direction, risk_atr, swing, zone_lookback):
    left = max(0, i - zone_lookback)
    swings = df.High.iloc[left:i][df.swing_high.iloc[left:i]] if direction == 1 else df.Low.iloc[left:i][df.swing_low.iloc[left:i]]
    broken = swings[swings < df.Close.iloc[i]] if direction == 1 else swings[swings > df.Close.iloc[i]]
    if broken.empty:
        return None
    top = bottom = None
    for j in range(i, max(0, i-zone_lookback), -1):
        if direction == 1 and pd.notna(df.demand_top.iloc[j]):
            top, bottom = df.demand_top.iloc[j], df.demand_bottom.iloc[j]; break
        if direction == -1 and pd.notna(df.supply_top.iloc[j]):
            top, bottom = df.supply_top.iloc[j], df.supply_bottom.iloc[j]; break
    if top is None or not (abs(df.Close.iloc[i] - broken.iloc[-1]) <= NEAR*risk_atr or bottom <= df.Close.iloc[i] <= top):
        return None
    entry, stop = (top + SL_BUFFER*risk_atr, bottom - SL_BUFFER*risk_atr) if direction == 1 else (bottom - SL_BUFFER*risk_atr, top + SL_BUFFER*risk_atr)
    distance = abs(entry-stop)
    if distance < .3*risk_atr:
        return None
    target = entry + direction * distance * RR
    return entry, stop, target, distance


def touched(bar, price):
    return bar.Low <= price <= bar.High


def _stop_hit(bar, direction, stop):
    return bar.Low <= stop if direction == 1 else bar.High >= stop


def _target_hit(bar, direction, target):
    return bar.High >= target if direction == 1 else bar.Low <= target


def simulate(df, signal_i, direction, entry, stop, target, distance, max_wait, managed, fee_bps=0, slippage_bps=0):
    """Return total R, or None for an unfilled/unresolved signal.

    The thresholds match execution/trade_manager.py: breakeven at 0.5R,
    TP1 at 1R (close 50%), then a one-original-stop trailing distance.
    Fees/slippage are expressed in basis points of entry price, converted to R.
    """
    fill_i = None
    for j in range(signal_i + 1, min(len(df), signal_i + max_wait + 1)):
        if touched(df.iloc[j], entry):
            fill_i = j; break
    if fill_i is None:
        return None
    cost_r = (2 * fee_bps + 2 * slippage_bps) / 10_000 * entry / distance
    if not managed:
        for j in range(fill_i, len(df)):
            bar = df.iloc[j]
            if _stop_hit(bar, direction, stop):
                return -1.0 - cost_r
            if _target_hit(bar, direction, target):
                return RR - cost_r
        return None
    active_stop, tp1_hit, result = stop, False, 0.0
    be_price, tp1 = entry + direction*.5*distance, entry + direction*TP1_FRACTION*(target-entry)
    for j in range(fill_i, len(df)):
        bar = df.iloc[j]
        # Conservative collision rule: an active stop is checked before advances.
        if _stop_hit(bar, direction, active_stop):
            remaining = 1 - TP1_CLOSE if tp1_hit else 1.0
            return result + remaining * ((active_stop-entry)*direction/distance) - cost_r
        if not tp1_hit and _target_hit(bar, direction, be_price):
            active_stop = entry
        if not tp1_hit and _target_hit(bar, direction, tp1):
            result += TP1_CLOSE * ((tp1-entry)*direction/distance)
            tp1_hit = True
            active_stop = max(active_stop, tp1-TRAIL*distance) if direction == 1 else min(active_stop, tp1+TRAIL*distance)
        if tp1_hit:
            extreme = bar.High if direction == 1 else bar.Low
            candidate = extreme - direction*TRAIL*distance
            active_stop = max(active_stop, candidate) if direction == 1 else min(active_stop, candidate)
            if _target_hit(bar, direction, target):
                return result + (1-TP1_CLOSE)*RR - cost_r
    return None


def run(df1, df5, swing=SWING, zone_lookback=ZONE_LOOKBACK, cooldown=COOLDOWN, managed=True, fee_bps=0, slippage_bps=0):
    df5 = zones(df5, MIN_ZONE)
    one_hour = df1[["ema", "atr", "trend"]].rename(columns=lambda c: f"{c}_1h")
    merged = pd.merge_asof(df5.reset_index(), one_hour.reset_index(), on="datetime", direction="backward").set_index("datetime")
    outcomes, fired, filled, last = [], 0, 0, {}
    for i in range(swing + MIN_ZONE + 5, len(merged)):
        row = merged.iloc[i]
        if pd.isna(row.atr_1h) or row.atr_1h <= 0:
            continue
        strength = abs(row.Close-row.ema_1h) / row.atr_1h
        # Match the existing 5M research harness and current live configuration:
        # all three labelled strengths are admitted.  The output must not be
        # compared with older Strong/Moderate-only 1H tests as if they matched.
        direction, now = int(row.trend_1h), merged.index[i]
        if direction in last and (now-last[direction]).total_seconds() < cooldown*3600:
            continue
        setup = signal(df5, i, direction, row.atr_1h, swing, zone_lookback)
        if not setup:
            continue
        fired += 1; last[direction] = now
        outcome = simulate(df5, i, direction, *setup, max_wait=12, managed=managed,
                           fee_bps=fee_bps, slippage_bps=slippage_bps)
        if outcome is not None:
            filled += 1; outcomes.append(outcome)
    return outcomes, fired, filled


def summary(label, result):
    outcomes, fired, filled = result
    n = len(outcomes)
    win = sum(r > 0 for r in outcomes) / n * 100 if n else 0
    exp = sum(outcomes) / n if n else 0
    print(f"{label:32} trades={n:4}  win={win:5.1f}%  total_R={sum(outcomes):+7.2f}  expectancy={exp:+.3f}R  filled={filled}/{fired}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--end-days-ago", type=int, default=0)
    ap.add_argument("--swing-values", default="8,12,16")
    ap.add_argument("--zone-lookback-values", default="50,100,150")
    ap.add_argument("--cooldown-values", default="0,2,4,6,8")
    ap.add_argument("--fee-bps", type=float, default=7.5)
    ap.add_argument("--slippage-bps", type=float, default=2.5)
    ap.add_argument("--only", choices=("comparison", "swing", "zone", "cooldown", "costs"),
                    help="Run one section; useful for long historical windows.")
    args = ap.parse_args()
    print(f"Downloading {args.days} days ending {args.end_days_ago} days ago...")
    df1, df5 = enrich(fetch("BTCUSDT", "1h", args.days, args.end_days_ago), SWING), enrich(fetch("BTCUSDT", "5m", args.days, args.end_days_ago), max(map(int, args.swing_values.split(','))))
    if args.only in (None, "comparison"):
        print("\nExit model comparison (identical all-strength 5M-entry signals):")
        summary("Single SL/TP (historical model)", run(df1, df5, managed=False))
        summary("Live-equivalent managed exit", run(df1, df5, managed=True))
    if args.only in (None, "swing"):
        print("\nSWING_LOOKBACK_5M sweep (managed exit):")
        for value in map(int, args.swing_values.split(',')):
            summary(f"SWING_LOOKBACK_5M={value}", run(df1, df5, swing=value))
    if args.only in (None, "zone"):
        print("\nZONE_LOOKBACK_5M sweep (managed exit):")
        for value in map(int, args.zone_lookback_values.split(',')):
            summary(f"ZONE_LOOKBACK_5M={value}", run(df1, df5, zone_lookback=value))
    if args.only in (None, "cooldown"):
        print("\nMIN_SIGNAL_GAP_HOURS sweep (managed exit):")
        for value in map(int, args.cooldown_values.split(',')):
            summary(f"MIN_SIGNAL_GAP_HOURS={value}", run(df1, df5, cooldown=value))
    if args.only in (None, "costs"):
        summary(f"Costs: fees {args.fee_bps}bps + slippage {args.slippage_bps}bps", run(df1, df5, managed=True, fee_bps=args.fee_bps, slippage_bps=args.slippage_bps))


if __name__ == "__main__":
    main()
