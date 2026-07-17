"""
notifications/telegram.py — all Telegram message sending and formatting.
"""
import requests
from datetime import datetime, timezone
from config import TELEGRAM_TOKEN, CHAT_ID, USD_QUOTE_2DP, ACCOUNT_SIZE, LOT_SIZE


def send_message(text):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        if resp.json().get("ok"):
            print(f"✅ Sent: {text[:60]}...")
        else:
            print(f"⚠️  Telegram error: {resp.json()}")
    except Exception as e:
        print(f"⚠️  Telegram failed: {e}")


def fmt(symbol, price):
    return f"${price:,.2f}" if symbol in USD_QUOTE_2DP else f"{price:.5f}"


def notify_signal(symbol, direction, entry, sl, tp, zone_top, zone_bot, trend):
    emoji  = "🟢" if direction == "BUY" else "🔴"
    arrow  = "📈" if direction == "BUY" else "📉"
    action = "BUY  🟢 LONG" if direction == "BUY" else "SELL 🔴 SHORT"
    sl_dist = abs(entry - sl)
    tp_dist = abs(tp - entry)
    rr = round(tp_dist / sl_dist, 1) if sl_dist > 0 else 0
    msg = f"""
{emoji} <b>{action} — {symbol}</b> {arrow}
🧭 <b>Trend strength: {trend}</b>

📍 <b>Entry:</b>  {fmt(symbol, entry)}
🛑 <b>Stop Loss:</b>  {fmt(symbol, sl)}
🎯 <b>Take Profit:</b>  {fmt(symbol, tp)}
⚖️ <b>Risk/Reward:</b>  1:{rr}

📦 <b>1H Zone:</b>  {fmt(symbol, zone_bot)} — {fmt(symbol, zone_top)}
⏰ <b>Time:</b>  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC

⚠️ <i>Verify on chart before entering</i>
"""
    send_message(msg.strip())


def notify_breakeven(symbol, direction, entry, current):
    action = "BUY 🟢" if direction == "BUY" else "SELL 🔴"
    msg = f"""
🔒 <b>BREAKEVEN — {symbol} | {action}</b>

📍 Entry:   {fmt(symbol, entry)}
💹 Current: {fmt(symbol, current)}
🛑 SL moved to entry: {fmt(symbol, entry)}

✅ <b>You cannot lose on this trade now</b>

⏰ {datetime.now(timezone.utc).strftime('%H:%M')} UTC
"""
    send_message(msg.strip())


def notify_in_profit(symbol, direction, entry, current, tp):
    action = "BUY 🟢" if direction == "BUY" else "SELL 🔴"
    tp_dist = abs(tp - entry)
    pct = abs(current - entry) / tp_dist * 100 if tp_dist > 0 else 0
    msg = f"""
💰 <b>IN PROFIT — {symbol} | {action}</b>

📍 Entry:    {fmt(symbol, entry)}
💹 Current:  {fmt(symbol, current)}
🎯 TP:       {fmt(symbol, tp)}  ({pct:.0f}% of the way there)

💡 SL already at breakeven — zero risk remaining

⏰ {datetime.now(timezone.utc).strftime('%H:%M')} UTC
"""
    send_message(msg.strip())


def notify_approaching_tp(symbol, direction, entry, current, tp):
    action = "BUY 🟢" if direction == "BUY" else "SELL 🔴"
    msg = f"""
⚠️ <b>APPROACHING TP — {symbol} | {action}</b>

📍 Entry:      {fmt(symbol, entry)}
💹 Current:    {fmt(symbol, current)}
🎯 TP:         {fmt(symbol, tp)}

🔔 <b>Take profit almost hit — get ready!</b>

⏰ {datetime.now(timezone.utc).strftime('%H:%M')} UTC
"""
    send_message(msg.strip())


def notify_tp_hit(symbol, direction, entry, tp, pnl_usd):
    action = "BUY 🟢" if direction == "BUY" else "SELL 🔴"
    pct    = pnl_usd / ACCOUNT_SIZE * 100
    msg = f"""
🎯 <b>TAKE PROFIT HIT — {symbol} | {action}</b> ✅

📍 Entry: {fmt(symbol, entry)}
🎯 TP:    {fmt(symbol, tp)}

💵 <b>P&L: +${pnl_usd:,.2f}</b>  ({pct:+.2f}% of account)

🏆 <b>Winning trade closed!</b>

⏰ {datetime.now(timezone.utc).strftime('%H:%M')} UTC
"""
    send_message(msg.strip())


def notify_sl_hit(symbol, direction, entry, sl, sl_moved, pnl_usd):
    action = "BUY 🟢" if direction == "BUY" else "SELL 🔴"
    tag = "STOPPED AT BREAKEVEN" if sl_moved else "STOP LOSS HIT"
    pct = pnl_usd / ACCOUNT_SIZE * 100
    msg = f"""
🛑 <b>{tag} — {symbol} | {action}</b>

📍 Entry: {fmt(symbol, entry)}
🛑 Exit:  {fmt(symbol, sl)}

💵 <b>P&L: ${pnl_usd:,.2f}</b>  ({pct:+.2f}% of account)

⏰ {datetime.now(timezone.utc).strftime('%H:%M')} UTC
"""
    send_message(msg.strip())
