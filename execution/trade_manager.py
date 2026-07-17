"""Monitor open trades and close the full position at its fixed SL or TP."""
import time
from config import RR_RATIO, BREAKEVEN_ATR_MULT, PROFIT_ALERT_ATR_MULT, APPROACHING_ATR_MULT, \
    CONTRACT_SIZE, LOT_SIZE
from data.binance_client import get_current_price
from notifications.telegram import fmt, notify_breakeven, notify_in_profit, notify_approaching_tp, \
    notify_tp_hit, notify_sl_hit
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
        ref = abs(tp - entry) / RR_RATIO

        if direction == 'BUY':
            profit = current - entry; remaining = tp - current
            sl_hit = current <= sl; tp_hit = current >= tp
        else:
            profit = entry - current; remaining = current - tp
            sl_hit = current >= sl; tp_hit = current <= tp

        print(f"  📊 {symbol} {direction} | Current: {fmt(symbol, current)} | Profit: {profit:+.2f}")

        if profit >= BREAKEVEN_ATR_MULT*ref and not trade['notified_breakeven']:
            notify_breakeven(symbol, direction, entry, current)
            trade['notified_breakeven'] = True

        if profit >= PROFIT_ALERT_ATR_MULT*ref and not trade['notified_profit']:
            notify_in_profit(symbol, direction, entry, current, tp)
            trade['notified_profit'] = True

        if 0 < remaining <= APPROACHING_ATR_MULT*ref and not trade['notified_approaching']:
            notify_approaching_tp(symbol, direction, entry, current, tp)
            trade['notified_approaching'] = True

        if tp_hit:
            price_move = (tp - entry) if direction == 'BUY' else (entry - tp)
            pnl_usd = calc_pnl_usd(symbol, price_move)
            notify_tp_hit(symbol, direction, entry, tp, pnl_usd)
            log_trade_to_journal(symbol, direction, entry, tp, pnl_usd, 'WIN')
            del active_trades[symbol]
        elif sl_hit:
            price_move = (sl - entry) if direction == 'BUY' else (entry - sl)
            pnl_usd = calc_pnl_usd(symbol, price_move)
            notify_sl_hit(symbol, direction, entry, sl, False, pnl_usd)
            log_trade_to_journal(symbol, direction, entry, sl, pnl_usd, 'LOSS')
            del active_trades[symbol]

        save_trades()
        time.sleep(1)
