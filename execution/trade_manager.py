"""
execution/trade_manager.py — monitors open trades, handles breakeven,
partial close, trailing stop, and final exits. Manual execution only —
this bot has no live broker connection, it tells the person what to do.
"""
import time
from config import RR_RATIO, BREAKEVEN_ATR_MULT, PROFIT_ALERT_ATR_MULT, APPROACHING_ATR_MULT, \
    TP1_CLOSE_PCT, TRAIL_ATR_MULT, CONTRACT_SIZE, LOT_SIZE
from data.binance_client import get_current_price
from notifications.telegram import fmt, notify_breakeven, notify_in_profit, notify_approaching_tp, \
    notify_partial_close, notify_tp_hit, notify_sl_hit
from execution.journal import log_trade_to_journal
from storage import active_trades, save_trades


def calc_pnl_usd(symbol, price_move):
    return price_move * CONTRACT_SIZE.get(symbol, 1) * LOT_SIZE


def monitor_active_trades():
    for symbol, trade in list(active_trades.items()):
        current = get_current_price(symbol)
        if current is None:
            continue
        entry, sl, tp = trade['entry'], trade['sl'], trade['tp']
        direction = trade['direction']
        sl_moved  = trade['sl_moved_to_entry']
        tp1_price = trade['tp1_price']
        tp1_hit   = trade['tp1_hit']
        remaining_pct = trade['remaining_pct']
        sl_dist_orig  = trade['sl_dist_original']
        ref = abs(tp - entry) / RR_RATIO

        if direction == 'BUY':
            profit = current - entry; remaining = tp - current
            sl_hit = current <= sl; tp_hit = current >= tp
            tp1_reached = current >= tp1_price
        else:
            profit = entry - current; remaining = current - tp
            sl_hit = current >= sl; tp_hit = current <= tp
            tp1_reached = current <= tp1_price

        print(f"  📊 {symbol} {direction} | Current: {fmt(symbol, current)} | Profit: {profit:+.2f}"
              f"{' | TRAILING' if tp1_hit else ''}")

        # ── Breakeven (only before TP1) ──────────────────────────
        if not tp1_hit and profit >= BREAKEVEN_ATR_MULT*ref and not trade['notified_breakeven']:
            notify_breakeven(symbol, direction, entry, current)
            trade['notified_breakeven'] = True
            trade['sl_moved_to_entry']  = True
            trade['sl'] = entry
            sl = entry

        if profit >= PROFIT_ALERT_ATR_MULT*ref and not trade['notified_profit']:
            notify_in_profit(symbol, direction, entry, current, tp)
            trade['notified_profit'] = True

        if not tp1_hit and 0 < remaining <= APPROACHING_ATR_MULT*ref and not trade['notified_approaching']:
            notify_approaching_tp(symbol, direction, entry, current, tp)
            trade['notified_approaching'] = True

        # ── TP1 — partial close + start trailing (manual action required) ──
        if not tp1_hit and tp1_reached:
            price_move = (tp1_price - entry) if direction == 'BUY' else (entry - tp1_price)
            partial_pnl = calc_pnl_usd(symbol, price_move) * TP1_CLOSE_PCT

            if direction == 'BUY':
                trail_sl = current - TRAIL_ATR_MULT * sl_dist_orig
            else:
                trail_sl = current + TRAIL_ATR_MULT * sl_dist_orig

            notify_partial_close(symbol, direction, entry, current, partial_pnl, trail_sl)
            log_trade_to_journal(symbol, direction, entry, tp1_price, partial_pnl, 'PARTIAL')

            trade['tp1_hit'] = True
            trade['remaining_pct'] = 1.0 - TP1_CLOSE_PCT
            trade['sl'] = trail_sl
            trade['sl_moved_to_entry'] = True
            sl, tp1_hit, remaining_pct = trail_sl, True, trade['remaining_pct']

        # ── Trail the stop silently once TP1 has happened ───────────
        elif tp1_hit:
            if direction == 'BUY':
                new_trail = current - TRAIL_ATR_MULT * sl_dist_orig
                if new_trail > sl:
                    trade['sl'] = new_trail
                    sl = new_trail
            else:
                new_trail = current + TRAIL_ATR_MULT * sl_dist_orig
                if new_trail < sl:
                    trade['sl'] = new_trail
                    sl = new_trail

        # ── Final exits ──────────────────────────────────────────
        if tp_hit:
            price_move = (tp - entry) if direction == 'BUY' else (entry - tp)
            pnl_usd = calc_pnl_usd(symbol, price_move) * remaining_pct
            notify_tp_hit(symbol, direction, entry, tp, pnl_usd, remaining_pct)
            log_trade_to_journal(symbol, direction, entry, tp, pnl_usd, 'WIN')
            del active_trades[symbol]
        elif sl_hit:
            price_move = (sl - entry) if direction == 'BUY' else (entry - sl)
            if tp1_hit:
                pnl_usd = calc_pnl_usd(symbol, price_move) * remaining_pct
                result = 'WIN' if pnl_usd > 0 else ('BREAKEVEN' if abs(pnl_usd) < 1 else 'LOSS')
            else:
                pnl_usd = 0.0 if sl_moved else calc_pnl_usd(symbol, price_move)
                result  = 'BREAKEVEN' if sl_moved else 'LOSS'
            notify_sl_hit(symbol, direction, entry, sl, sl_moved, pnl_usd, tp1_hit, remaining_pct)
            log_trade_to_journal(symbol, direction, entry, sl, pnl_usd, result)
            del active_trades[symbol]

        save_trades()
        time.sleep(1)
