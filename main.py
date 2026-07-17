"""
main.py — entry point. Wires all modules together, runs the scan/monitor
loops on schedule.
"""
import time
import schedule
import requests
import pandas as pd
from datetime import datetime, timezone

from config import TELEGRAM_TOKEN, SYMBOLS, MONITOR_INTERVAL, SIGNAL_INTERVAL
from data.binance_client import fetch_candles
from strategy.indicators import calculate_indicators
from strategy.zones import detect_zones
from strategy.signals import check_for_signal, is_new_candle, mark_candle_processed, \
    already_alerted, mark_alerted
from notifications.telegram import send_message, notify_signal
from execution.trade_manager import monitor_active_trades
from execution.journal import send_daily_summary
from storage import active_trades, save_trades, load_trades, load_signal_state


def monitor_loop():
    """Fast loop — checks open trades for their fixed SL/TP levels."""
    if active_trades:
        print(f"\n💹 Monitor — {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
        monitor_active_trades()


def scan_for_signals():
    """Evaluate 5M entries using completed 1H candles only as trend context."""
    print(f"\n🔍 5M entry scan — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")

    for symbol in SYMBOLS:
        if symbol in active_trades:
            continue

        df_1h = fetch_candles(symbol, "1h")
        df_5m = fetch_candles(symbol, "5min")
        if df_1h is None or df_5m is None:
            continue

        # Exclude the still-forming bars.  The 1H series supplies directional
        # context only; zones, broken levels, and the entry trigger are 5M.
        df_1h = calculate_indicators(df_1h.iloc[:-1])
        df_5m = calculate_indicators(df_5m.iloc[:-1])
        if df_1h.empty or df_5m.empty:
            continue
        context = df_1h[['ema100', 'atr', 'trend']].rename(
            columns={'ema100': 'ema100_1h', 'atr': 'atr_1h', 'trend': 'trend_1h'}
        )
        df = pd.merge_asof(
            df_5m.reset_index(), context.reset_index(), on='datetime', direction='backward'
        ).set_index('datetime')
        if df[['ema100_1h', 'atr_1h', 'trend_1h']].iloc[-1].isna().any():
            continue
        df['ema100'] = df.pop('ema100_1h')
        df['atr'] = df.pop('atr_1h')
        df['trend'] = df.pop('trend_1h').astype(int)
        df = detect_zones(df)

        if not is_new_candle(symbol, "5min", df):
            print(f"  ⏭  {symbol} — candle already evaluated, skipping")
            continue

        signal, reason = check_for_signal(df)
        mark_candle_processed(symbol, "5min", df)

        if signal is None:
            print(f"  ○  {symbol} — {reason}")
            continue

        direction = signal['direction']
        if already_alerted(symbol, direction):
            print(f"  ⏭  {symbol} — already alerted")
            continue

        notify_signal(symbol, direction, signal['entry'], signal['sl'], signal['tp'],
                      signal['zone_top'], signal['zone_bot'], signal['trend'])

        entry, sl, tp = signal['entry'], signal['sl'], signal['tp']

        active_trades[symbol] = {
            'direction': direction, 'entry': entry, 'sl': sl, 'tp': tp,
            'open_time': datetime.now(timezone.utc).isoformat(),
            'notified_profit': False,
            'notified_approaching': False,
            'notified_breakeven': False,
        }
        mark_alerted(symbol, direction)
        save_trades()
        print(f"  🟢 New {direction} signal: {symbol} ({signal['trend']})")
        time.sleep(1)


def send_startup():
    send_message(f"""
🤖 <b>Nadtrade BTC Bot v9 is LIVE</b>

Data provider: Binance (public API, no key needed)
Strategy: Strong/Moderate/Weak — all trend strengths (testing signal frequency)
Monitoring: <b>{' · '.join(SYMBOLS)}</b> — 24/7, no session restrictions
Entries: 5M triggers with 1H trend context
Exits: fixed full-position stop loss / take profit

📓 Daily journal sends at 21:00 UTC (00:00 Addis)

✅ Started {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC
""".strip())


if __name__ == "__main__":
    print("\n🤖 NADTRADE BTC BOT v9 — 5M Entries + Fixed SL/TP")
    print("=" * 60)

    test = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe", timeout=10).json()
    if not test.get("ok"):
        print("❌ Invalid token"); exit()
    print(f"✅ Connected as: {test['result']['first_name']}")

    load_trades()
    load_signal_state()
    send_startup()
    scan_for_signals()

    schedule.every(MONITOR_INTERVAL).seconds.do(monitor_loop)
    schedule.every(SIGNAL_INTERVAL).seconds.do(scan_for_signals)
    schedule.every().day.at("21:00").do(send_daily_summary)
    schedule.every().hour.do(lambda: send_message(
        f"💓 Heartbeat — {datetime.now(timezone.utc).strftime('%H:%M')} UTC | Active: {len(active_trades)}"
    ))

    print(f"\n⏰ Monitoring every {MONITOR_INTERVAL}s · Signal scan every {SIGNAL_INTERVAL}s. Ctrl+C to stop.\n")
    while True:
        schedule.run_pending()
        time.sleep(1)
