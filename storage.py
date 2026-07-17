"""
storage.py — persistence layer. active_trades is the single shared source of
truth for open trades; other modules do `from storage import active_trades`
and mutate it in place (never reassign it directly) so all references stay
in sync. last_processed_candle and last_signal follow the same pattern for
the same reason: signals.py used to hold these as local module-level dicts,
which meant a restart silently wiped alert cooldowns and candle-freshness
tracking, allowing duplicate signals within MIN_SIGNAL_GAP_HOURS.
"""
import json
import os
import pandas as pd
from datetime import datetime
from config import TRADES_FILE, SIGNAL_STATE_FILE
from notifications.telegram import send_message, fmt

active_trades = {}

last_processed_candle = {}   # key: "{symbol}_{interval}" -> pd.Timestamp
last_signal = {}             # key: "{symbol}_{direction}" -> datetime


def save_trades():
    try:
        s = {sym: {**t, 'open_time': t['open_time'] if isinstance(t['open_time'], str) else t['open_time'].isoformat()}
             for sym, t in active_trades.items()}
        with open(TRADES_FILE, 'w') as f:
            json.dump(s, f, indent=2)
    except Exception as e:
        print(f"⚠️  Save failed: {e}")


def load_trades():
    if not os.path.exists(TRADES_FILE):
        return
    try:
        with open(TRADES_FILE, 'r') as f:
            data = json.load(f)
        active_trades.clear()
        active_trades.update(data)   # mutate in place — keeps other modules' references valid
        if active_trades:
            print(f"📂 Loaded {len(active_trades)} active trades")
            send_message(f"📂 <b>Bot restarted — trades restored</b>\n" +
                         "\n".join([f"{sym}: {t['direction']} @ {fmt(sym, t['entry'])}" for sym, t in active_trades.items()]))
    except Exception as e:
        print(f"⚠️  Load failed: {e}")


def save_signal_state():
    try:
        s = {
            'last_processed_candle': {k: str(v) for k, v in last_processed_candle.items()},
            'last_signal': {k: v.isoformat() for k, v in last_signal.items()},
        }
        with open(SIGNAL_STATE_FILE, 'w') as f:
            json.dump(s, f, indent=2)
    except Exception as e:
        print(f"⚠️  Signal state save failed: {e}")


def load_signal_state():
    if not os.path.exists(SIGNAL_STATE_FILE):
        return
    try:
        with open(SIGNAL_STATE_FILE, 'r') as f:
            data = json.load(f)
        last_processed_candle.clear()
        last_processed_candle.update({k: pd.Timestamp(v) for k, v in data.get('last_processed_candle', {}).items()})
        last_signal.clear()
        last_signal.update({k: datetime.fromisoformat(v) for k, v in data.get('last_signal', {}).items()})
        if last_processed_candle or last_signal:
            print(f"📂 Loaded signal state — {len(last_processed_candle)} candle marks, {len(last_signal)} cooldowns")
    except Exception as e:
        print(f"⚠️  Signal state load failed: {e}")