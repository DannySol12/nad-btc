"""
main.py — entry point. Wires all modules together, runs the scan/monitor
loops on schedule.
"""
import time
import schedule
import requests
from datetime import datetime, timezone

from config import TELEGRAM_TOKEN, SYMBOLS, SIGNAL_INTERVAL_TF, MONITOR_INTERVAL, SIGNAL_INTERVAL, \
    TP1_FRACTION
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
    """Fast loop — only checks open trades for breakeven/TP/SL. Cheap: 1 API call max."""
    if active_trades:
        print(f"\n💹 Monitor — {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
        monitor_active_trades()


def scan_for_signals():
    """Single-timeframe scan — Strong/Moderate/Weak trend model, 1H candles."""
    print(f"\n🔍 Signal scan — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")

    for symbol in SYMBOLS:
        if symbol in active_trades:
            continue

        df = fetch_candles(symbol, SIGNAL_INTERVAL_TF)
        if df is None:
            continue
        df = calculate_indicators(df)
        df = detect_zones(df)

        if not is_new_candle(symbol, SIGNAL_INTERVAL_TF, df):
            print(f"  ⏭  {symbol} — candle already evaluated, skipping")
            continue

        signal, reason = check_for_signal(df)
        mark_candle_processed(symbol, SIGNAL_INTERVAL_TF, df)

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
        tp1_price = entry + TP1_FRACTION * (tp - entry) if direction == 'BUY' \
                    else entry - TP1_FRACTION * (entry - tp)

        active_trades[symbol] = {
            'direction': direction, 'entry': entry, 'sl': sl, 'tp': tp,
            'open_time': datetime.now(timezone.utc).isoformat(),
            'notified_breakeven': False, 'notified_profit': False,
            'notified_approaching': False, 'sl_moved_to_entry': False,
            'tp1_price': tp1_price, 'tp1_hit': False, 'remaining_pct': 1.0,
            'sl_dist_original': abs(entry - sl),
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
Partial close at 50% + trailing stop (manual execution)

📓 Daily journal sends at 21:00 UTC (00:00 Addis)

✅ Started {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC
""".strip())


if __name__ == "__main__":
    print("\n🤖 NADTRADE BTC BOT v9 — All Trend Strengths + Partial Close/Trailing")
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