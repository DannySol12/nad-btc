"""
execution/journal.py — trade logging and daily P&L summary.
"""
import json
import os
from datetime import datetime, timezone
from config import JOURNAL_FILE, TZ_OFFSETS
from notifications.telegram import send_message


def log_trade_to_journal(symbol, direction, entry, exit_price, pnl_usd, result):
    trade = {
        'time': datetime.now(timezone.utc).strftime('%H:%M UTC'), 'symbol': symbol,
        'direction': direction, 'entry': round(entry, 5), 'exit': round(exit_price, 5),
        'pnl_usd': round(pnl_usd, 2), 'result': result
    }
    try:
        journal = {}
        if os.path.exists(JOURNAL_FILE):
            with open(JOURNAL_FILE, 'r') as f:
                journal = json.load(f)
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        journal.setdefault(today, []).append(trade)
        with open(JOURNAL_FILE, 'w') as f:
            json.dump(journal, f, indent=2)
    except Exception as e:
        print(f"⚠️  Journal save failed: {e}")


def send_daily_summary():
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    addis_hr = (datetime.now(timezone.utc).hour + TZ_OFFSETS['Addis Ababa']) % 24
    try:
        if not os.path.exists(JOURNAL_FILE):
            send_message(f"📓 <b>Daily Journal — {today}</b>\n\nNo trades today.")
            return
        with open(JOURNAL_FILE, 'r') as f:
            journal = json.load(f)
        trades = journal.get(today, [])
    except:
        trades = []

    if not trades:
        send_message(f"📓 <b>Daily Journal — {today}</b>\n\nNo completed trades today.")
        return

    wins      = [t for t in trades if t['result'] == 'WIN']
    losses    = [t for t in trades if t['result'] == 'LOSS']
    bes       = [t for t in trades if t['result'] == 'BREAKEVEN']
    partials  = [t for t in trades if t['result'] == 'PARTIAL']
    closed_trades = [t for t in trades if t['result'] != 'PARTIAL']
    total  = sum(t['pnl_usd'] for t in trades)
    wr     = (len(wins) / len(closed_trades) * 100) if closed_trades else 0
    best   = max(trades, key=lambda x: x['pnl_usd'])
    worst  = min(trades, key=lambda x: x['pnl_usd'])

    def emoji_for(result):
        return {'WIN': '✅', 'BREAKEVEN': '🔒', 'PARTIAL': '✂️'}.get(result, '❌')

    lines = "\n".join([
        f"{emoji_for(t['result'])} "
        f"{t['symbol']} {t['direction']} | ${t['pnl_usd']:+.2f}"
        for t in trades
    ])
    pnl_emoji = "🟢" if total >= 0 else "🔴"

    msg = f"""
📓 <b>DAILY JOURNAL — {today}</b>
🕐 Addis: {addis_hr:02d}:00 EAT

{pnl_emoji} <b>Total P&L: ${total:+.2f}</b>

📊 Trades: {len(closed_trades)}  Wins: {len(wins)} ✅  Losses: {len(losses)} ❌  Breakeven: {len(bes)} 🔒  Partial closes: {len(partials)} ✂️
Win rate: {wr:.0f}%

🏆 Best:  {best['symbol']} ${best['pnl_usd']:+.2f}
💔 Worst: {worst['symbol']} ${worst['pnl_usd']:+.2f}

📋 <b>Trade log:</b>
{lines}
"""
    send_message(msg.strip())
    print(f"📓 Daily journal sent for {today}")
