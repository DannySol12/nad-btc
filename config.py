"""
config.py — all settings in one place. Every other module imports from here.
"""

# ── Telegram / credentials — fill in your own, keep private ──
TELEGRAM_TOKEN = "8878126696:AAGDJtlbymJQ4AeuXPsxWEE7WvhPBYL3-MM"
CHAT_ID        = "350629996"

# ── Symbols ──
SYMBOLS        = ["BTC/USD"]
USD_QUOTE_2DP  = ["BTC/USD"]
BINANCE_SYMBOL = {"BTC/USD": "BTCUSDT"}
BINANCE_INTERVAL = {"1h": "1h", "5min": "5m"}

SIGNAL_INTERVAL_TF = "1h"

# Testing all trend strengths — signal frequency was too low with Strong/Moderate
# only. Backtest evidence showed Weak underperforms (27.5% win rate, -$1,942
# P&L) — revisit this if signal quality drops.
ALLOWED_TREND_STRENGTHS = ["Strong", "Moderate", "Weak"]

# ── Indicator / zone parameters ──
EMA_PERIOD       = 100
ATR_PERIOD       = 14
MIN_ZONE_CANDLES = 6
SWING_LOOKBACK   = 10
ZONE_LOOKBACK    = 50
RR_RATIO         = 2.0

# ── Timing ──
MONITOR_INTERVAL = 45      # seconds — checks open trades for breakeven/TP/SL
SIGNAL_INTERVAL  = 300     # seconds — checks for new setups

# ── Persistence ──
TRADES_FILE       = "btc_active_trades_v9.json"
JOURNAL_FILE      = "btc_journal_v9.json"
SIGNAL_STATE_FILE = "btc_signal_state_v9.json"

# ── Signal / trade-management thresholds (in ATR multiples) ──
NEAR_LEVEL_ATR_MULT   = 0.5
SL_BUFFER_ATR_MULT    = 0.2
BREAKEVEN_ATR_MULT    = 0.5
PROFIT_ALERT_ATR_MULT = 1.0
APPROACHING_ATR_MULT  = 0.3
MIN_SIGNAL_GAP_HOURS  = 4

# ── Partial close + trailing stop — manual execution ──
TP1_FRACTION   = 0.5
TP1_CLOSE_PCT  = 0.5
TRAIL_ATR_MULT = 1.0

# ── Misc ──
TZ_OFFSETS = {"Addis Ababa": 3}

# ── Position sizing — confirm CONTRACT_SIZE against your actual broker ──
ACCOUNT_SIZE  = 10000
LOT_SIZE      = 1.0
CONTRACT_SIZE = {"BTC/USD": 1}
