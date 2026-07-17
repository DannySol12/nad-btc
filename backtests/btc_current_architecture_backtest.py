"""Two-year BTCUSDT backtest for the committed live architecture.

It uses the same 1H-context/5M-entry construction and fixed full-position
SL/TP outcome as ``main.py`` and ``execution/trade_manager.py``.  Historical
fills are conservative: an entry must trade within the next 12 five-minute
candles and an OHLC bar touching both SL and TP is scored as SL first.
"""
import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btc_5m_exit_backtest as engine
from config import (
    ALLOWED_TREND_STRENGTHS,
    ATR_PERIOD,
    EMA_PERIOD,
    MIN_SIGNAL_GAP_HOURS,
    MIN_ZONE_CANDLES,
    RR_RATIO,
    SWING_LOOKBACK,
    ZONE_LOOKBACK,
)


def summarize(label, result):
    outcomes, fired, resolved = result
    trades = len(outcomes)
    wins = sum(outcome > 0 for outcome in outcomes)
    win_rate = wins / trades * 100 if trades else 0
    expectancy = sum(outcomes) / trades if trades else 0
    print(f"{label}:\n"
          f"  signals fired: {fired}\n"
          f"  resolved fills: {resolved}\n"
          f"  trades: {trades}\n"
          f"  win rate: {win_rate:.1f}%\n"
          f"  total R: {sum(outcomes):+.2f}R\n"
          f"  expectancy: {expectancy:+.3f}R per trade")


def run_current(df_1h, df_5m, fee_bps=0, slippage_bps=0):
    return engine.run(
        df_1h, df_5m,
        swing=SWING_LOOKBACK,
        zone_lookback=ZONE_LOOKBACK,
        cooldown=MIN_SIGNAL_GAP_HOURS,
        managed=False,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
    )


def compact_summary(label, result):
    outcomes, fired, resolved = result
    trades = len(outcomes)
    win_rate = sum(outcome > 0 for outcome in outcomes) / trades * 100 if trades else 0
    expectancy = sum(outcomes) / trades if trades else 0
    print(f"{label:30} {trades:5} {win_rate:8.1f}% {sum(outcomes):+9.2f}R {expectancy:+10.3f}R {resolved:4}/{fired}")


def prepare(df_1h_raw, df_5m_raw):
    """Build the live 1H-context / 5M-entry arrays without repeated pandas scans."""
    df_1h = df_1h_raw.copy()
    tr = pd.concat([
        df_1h.High - df_1h.Low,
        (df_1h.High - df_1h.Close.shift()).abs(),
        (df_1h.Low - df_1h.Close.shift()).abs(),
    ], axis=1).max(axis=1)
    context = pd.DataFrame({
        "ema": df_1h.Close.ewm(span=EMA_PERIOD, adjust=False).mean(),
        "atr": tr.ewm(span=ATR_PERIOD, adjust=False).mean(),
    }, index=df_1h.index)
    context["trend"] = np.where(df_1h.Close > context.ema, 1, -1)
    merged = pd.merge_asof(
        df_5m_raw.reset_index(), context.reset_index(), on="datetime", direction="backward"
    ).set_index("datetime")
    return merged


def run_fast(df):
    """Return fixed-SL/TP outcomes and per-trade cost coefficients in one pass."""
    open_, high, low, close = (df[column].to_numpy(dtype=float) for column in ("Open", "High", "Low", "Close"))
    atr, ema, trend = (df[column].to_numpy() for column in ("atr", "ema", "trend"))
    count = len(df)
    indices = np.arange(count)
    candles = np.ones(MIN_ZONE_CANDLES, dtype=int)
    bullish = np.zeros(count, dtype=bool)
    bearish = np.zeros(count, dtype=bool)
    bullish[MIN_ZONE_CANDLES:] = np.convolve((close > open_).astype(int), candles, mode="valid")[1:] == MIN_ZONE_CANDLES
    bearish[MIN_ZONE_CANDLES:] = np.convolve((close < open_).astype(int), candles, mode="valid")[1:] == MIN_ZONE_CANDLES
    demand_top = np.full(count, np.nan)
    demand_bottom = np.full(count, np.nan)
    supply_top = np.full(count, np.nan)
    supply_bottom = np.full(count, np.nan)
    zone_rows = indices[MIN_ZONE_CANDLES:]
    demand_top[zone_rows[bullish[MIN_ZONE_CANDLES:]]] = high[zone_rows[bullish[MIN_ZONE_CANDLES:]] - MIN_ZONE_CANDLES]
    demand_bottom[zone_rows[bullish[MIN_ZONE_CANDLES:]]] = low[zone_rows[bullish[MIN_ZONE_CANDLES:]] - MIN_ZONE_CANDLES]
    supply_top[zone_rows[bearish[MIN_ZONE_CANDLES:]]] = high[zone_rows[bearish[MIN_ZONE_CANDLES:]] - MIN_ZONE_CANDLES]
    supply_bottom[zone_rows[bearish[MIN_ZONE_CANDLES:]]] = low[zone_rows[bearish[MIN_ZONE_CANDLES:]] - MIN_ZONE_CANDLES]
    demand_last = np.maximum.accumulate(np.where(np.isfinite(demand_top), indices, -1))
    supply_last = np.maximum.accumulate(np.where(np.isfinite(supply_top), indices, -1))
    window = SWING_LOOKBACK * 2 + 1
    swing_high = high == pd.Series(high).rolling(window, center=True).max().to_numpy()
    swing_low = low == pd.Series(low).rolling(window, center=True).min().to_numpy()
    swing_high[:SWING_LOOKBACK] = swing_high[-SWING_LOOKBACK:] = False
    swing_low[:SWING_LOOKBACK] = swing_low[-SWING_LOOKBACK:] = False

    outcomes, cost_coefficients, fired, resolved = [], [], 0, 0
    last_signal = {1: -10**9, -1: -10**9}
    cooldown_bars = MIN_SIGNAL_GAP_HOURS * 12
    for i in range(SWING_LOOKBACK + MIN_ZONE_CANDLES + 5, count):
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        direction = int(trend[i])
        if i - last_signal[direction] < cooldown_bars:
            continue
        left = max(0, i - ZONE_LOOKBACK)
        if direction == 1:
            candidate = np.where(swing_high[left:i] & (high[left:i] < close[i]))[0]
            zone_i = demand_last[i]
        else:
            candidate = np.where(swing_low[left:i] & (low[left:i] > close[i]))[0]
            zone_i = supply_last[i]
        if not len(candidate) or zone_i < 0 or i - zone_i >= ZONE_LOOKBACK:
            continue
        broken_i = left + candidate[-1]
        zone_top = demand_top[zone_i] if direction == 1 else supply_top[zone_i]
        zone_bottom = demand_bottom[zone_i] if direction == 1 else supply_bottom[zone_i]
        if not (abs(close[i] - (high[broken_i] if direction == 1 else low[broken_i])) <= .5 * atr[i]
                or zone_bottom <= close[i] <= zone_top):
            continue
        entry, stop = ((zone_top + .2 * atr[i]), (zone_bottom - .2 * atr[i])) if direction == 1 else ((zone_bottom - .2 * atr[i]), (zone_top + .2 * atr[i]))
        distance = abs(entry - stop)
        if distance < .3 * atr[i]:
            continue
        target = entry + direction * distance * RR_RATIO
        fired += 1
        last_signal[direction] = i
        fill_i = next((j for j in range(i + 1, min(count, i + 13)) if low[j] <= entry <= high[j]), None)
        if fill_i is None:
            continue
        outcome = None
        for j in range(fill_i, count):
            stop_hit = low[j] <= stop if direction == 1 else high[j] >= stop
            target_hit = high[j] >= target if direction == 1 else low[j] <= target
            if stop_hit:
                outcome = -1.0
                break
            if target_hit:
                outcome = RR_RATIO
                break
        if outcome is not None:
            resolved += 1
            outcomes.append(outcome)
            cost_coefficients.append(2 * entry / distance / 10_000)
    return np.asarray(outcomes), np.asarray(cost_coefficients), fired, resolved


def result_with_cost(base_result, fee_bps=0, slippage_bps=0):
    outcomes, coefficients, fired, resolved = base_result
    return outcomes - coefficients * (fee_bps + slippage_bps), fired, resolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--end-days-ago", type=int, default=0)
    args = parser.parse_args()

    if ALLOWED_TREND_STRENGTHS != ["Strong", "Moderate", "Weak"]:
        raise RuntimeError("This backtest currently supports the live all-strength configuration only.")

    # The shared engine implements the same zones, broken levels, 1H ATR
    # risk sizing, fill window, and fixed SL-first ambiguity rule as the
    # earlier study.  Set its inputs from config so this report tracks the
    # committed bot rather than the former research defaults (4/12/100).
    engine.EMA = EMA_PERIOD
    engine.ATR = ATR_PERIOD
    engine.RR = RR_RATIO
    engine.MIN_ZONE = MIN_ZONE_CANDLES

    print(f"Loading {args.days} days of BTCUSDT 1H/5M candles...")
    raw_1h = engine.fetch("BTCUSDT", "1h", args.days, args.end_days_ago)
    raw_5m = engine.fetch("BTCUSDT", "5m", args.days, args.end_days_ago)
    df = prepare(raw_1h, raw_5m)
    base_result = run_fast(df)
    result = result_with_cost(base_result)
    print("\nCURRENT LIVE ARCHITECTURE — 1H context, 5M entries, fixed SL/TP")
    summarize("Two-year result", result)
    print("\nComparison reference — previous matched 365-day study (575 common resolved trades):")
    print("  Simple SL/TP:              36.2% win rate, +0.085R expectancy")
    print("  Breakeven → TP1 → trail:    25.0% win rate, -0.192R expectancy")
    print("\nThe two-year result above uses the current config values "
          f"(MIN_ZONE_CANDLES={MIN_ZONE_CANDLES}, SWING_LOOKBACK={SWING_LOOKBACK}, "
          f"ZONE_LOOKBACK={ZONE_LOOKBACK}, cooldown={MIN_SIGNAL_GAP_HOURS}h), so it is a "
          "validation of the committed bot, not a matched exit-model rerun.")

    print("\nCOST SENSITIVITY — fixed SL/TP, same two-year signals")
    print(f"{'assumption (per side)':30} {'trades':>5} {'win rate':>9} {'total R':>10} {'expectancy':>11} {'resolved/fired':>15}")
    for label, fee_bps, slippage_bps in [
        ("No trading costs", 0, 0),
        ("5.0bps fee + 1.0bps slippage", 5, 1),
        ("7.5bps fee + 2.5bps slippage", 7.5, 2.5),
        ("10.0bps fee + 5.0bps slippage", 10, 5),
    ]:
        compact_summary(label, result_with_cost(base_result, fee_bps, slippage_bps))

    midpoint = df.index[len(df) // 2]
    older, newer = df[df.index < midpoint], df[df.index >= midpoint]
    print("\nYEAR-BY-YEAR SPLIT — fixed SL/TP, no costs")
    print(f"Split point: {midpoint:%Y-%m-%d %H:%M} UTC")
    print(f"{'period':30} {'trades':>5} {'win rate':>9} {'total R':>10} {'expectancy':>11} {'resolved/fired':>15}")
    compact_summary(f"Earlier ({older.index[0]:%Y-%m-%d} to {older.index[-1]:%Y-%m-%d})", result_with_cost(run_fast(older)))
    compact_summary(f"Recent ({newer.index[0]:%Y-%m-%d} to {newer.index[-1]:%Y-%m-%d})", result_with_cost(run_fast(newer)))


if __name__ == "__main__":
    main()
