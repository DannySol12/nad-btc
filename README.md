# NAD-BTC: Automated Bitcoin Trading Bot

> **A Supply & Demand Zone Trading System for BTC/USD with Multi-Timeframe Analysis**

![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python&logoColor=white)
![Binance](https://img.shields.io/badge/Binance-Public%20API-F3BA2F?style=flat-square&logo=binance&logoColor=black)
![Telegram](https://img.shields.io/badge/Telegram-Notifications-26A5E4?style=flat-square&logo=telegram&logoColor=white)

---

## Table of Contents

- [What Is This?](#what-is-this)
- [The Trading Philosophy](#the-trading-philosophy)
- [How It Works (Visual Guide)](#how-it-works-visual-guide)
- [Strategy Deep Dive](#strategy-deep-dive)
- [Architecture Overview](#architecture-overview)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [File Structure](#file-structure)
- [Backtesting](#backtesting)
- [Risk Disclaimer](#risk-disclaimer)

---

## What Is This?

**NAD-BTC** is an automated trading bot that scans Bitcoin markets 24/7, identifies high-probability trade setups based on **Supply & Demand zones**, and sends you real-time alerts via Telegram.

### For Non-Technical Users

Think of this bot as your personal trading assistant that:
- Watches Bitcoin charts while you sleep
- Spots "bounce zones" where price is likely to reverse
- Sends you entry, stop loss, and take profit levels instantly
- Keeps a journal of every trade for review

### For Technical Users

A Python-based algorithmic trading system that:
- Fetches real-time candlestick data from Binance public API (no API key required)
- Implements multi-timeframe analysis (1H context + 5M precision entries)
- Uses EMA-100 trend detection with ATR-based volatility sizing
- Identifies institutional supply/demand zones via consecutive candle patterns
- Executes swing level breakout confirmations with zone proximity validation
- Maintains persistent state across restarts via JSON persistence layer

---

## The Trading Philosophy

### Core Concept: "Follow the Smart Money"

Large institutional traders (banks, hedge funds) don't buy randomly. They place orders at specific price levels where they expect the market to reverse. These levels create **Supply and Demand Zones**.

```
THE BIG IDEA:
═══════════════════════════════════════════════════════════════════

  When price returns to a zone where big traders previously
  entered aggressively, it often bounces again.

  Our bot finds these zones and alerts you when price approaches.
```

### Visual: What is a Supply/Demand Zone?

```
                    SUPPLY ZONE (Sellers are here)
                    ┌─────────────────────────────┐
                    │  ████  ████  ████           │  ← Price drops from here
                    │  ████  ████  ████           │     (Big traders sold)
   PRICE            │                             │
   ACTION           └─────────────────────────────┘
      │                                           │
      │                                           │
      │                                           │
      │                                           ▼
      │                                     ┌─────────────────────────────┐
      │                                     │  ░░░░  ░░░░  ░░░░           │  ← Price bounces from here
      │                                     │  ░░░░  ░░░░  ░░░░           │     (Big traders buy)
      │                                     │                             │
      │                                     └─────────────────────────────┘
      │                                       DEMAND ZONE (Buyers are here)
      │
      └──► TIME
```

### The Three Pillars of Our Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    STRATEGY PILLARS                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1️⃣  TREND DIRECTION          "Trade with the trend"               │
│     └── 1-Hour EMA-100 determines if we BUY or SELL                │
│                                                                     │
│  2️⃣  ZONE IDENTIFICATION     "Know where big players act"          │
│     └── Supply/Demand zones from 5-minute candle patterns           │
│                                                                     │
│  3️⃣  BREAKOUT CONFIRMATION   "Wait for price to prove itself"      │
│     └── Swing level must break before we enter                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## How It Works (Visual Guide)

### The Complete Trading Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        BOT OPERATIONAL FLOW                              │
└──────────────────────────────────────────────────────────────────────────┘

    ┌─────────────┐
    │   START     │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  STEP 1: FETCH MARKET DATA (Every 5 minutes)                       │
    │  ─────────────────────────────────────────────────────────────────  │
    │  • Download 300 candles of 1H data (trend context)                  │
    │  • Download 300 candles of 5M data (entry precision)                │
    │  • Source: Binance Public API (no key needed)                       │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  STEP 2: CALCULATE INDICATORS                                       │
    │  ─────────────────────────────────────────────────────────────────  │
    │  • EMA-100: Smoothed average price over 100 periods                 │
    │  • ATR-14: Average True Range (measures volatility)                 │
    │  • Trend: Price above EMA = BUY (+1), below = SELL (-1)            │
    │  • Swing Highs/Lows: Local peaks and valleys                        │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  STEP 3: DETECT ZONES                                               │
    │  ─────────────────────────────────────────────────────────────────  │
    │  • Find 4+ consecutive bullish candles → DEMAND ZONE                │
    │  • Find 4+ consecutive bearish candles → SUPPLY ZONE                │
    │  • Zone boundaries = High/Low of the candle BEFORE the sequence     │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  STEP 4: CHECK SIGNAL CONDITIONS                                    │
    │  ─────────────────────────────────────────────────────────────────  │
    │  ✓ Is trend strong enough? (Strong/Moderate/Weak allowed)          │
    │  ✓ Has a swing level been broken in the right direction?            │
    │  ✓ Is price near the broken level OR inside the zone?              │
    │  ✓ Is stop loss distance at least 0.3x ATR? (not too tight)        │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  STEP 5: CALCULATE TRADE LEVELS                                     │
    │  ─────────────────────────────────────────────────────────────────  │
    │  • ENTRY: Zone boundary ± buffer (0.2x ATR)                        │
    │  • STOP LOSS: Opposite zone boundary ∓ buffer                       │
    │  • TAKE PROFIT: Entry ± (Risk distance × 2.0)                       │
    │  • Risk/Reward Ratio: Always 1:2                                    │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  STEP 6: SEND TELEGRAM ALERT                                        │
    │  ─────────────────────────────────────────────────────────────────  │
    │  📱 Instant notification with:                                      │
    │     • Direction (BUY/SELL)                                          │
    │     • Entry price                                                   │
    │     • Stop Loss price                                               │
    │     • Take Profit price                                             │
    │     • Risk/Reward ratio                                             │
    │     • Trend strength                                                │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  STEP 7: MONITOR TRADE (Every 45 seconds)                          │
    │  ─────────────────────────────────────────────────────────────────  │
    │  • Check current price vs entry/sl/tp                               │
    │  • Send updates:                                                    │
    │     🔒 Breakeven alert (when profit ≥ 0.5R)                        │
    │     💰 In-profit alert (when profit ≥ 1.0R)                        │
    │     ⚠️ Approaching TP alert (within 0.3R of target)                │
    │     🎯 TP Hit (trade closed as WIN)                                 │
    │     🛑 SL Hit (trade closed as LOSS)                                │
    └─────────────────────────────────────────────────────────────────────┘
```

---

## Strategy Deep Dive

### 1. Trend Detection: The 1-Hour EMA

The **Exponential Moving Average (EMA)** is a smoothed price average that gives more weight to recent prices.

```
THE EMA CONCEPT:
═══════════════════════════════════════════════════════════════════

  Price ABOVE the EMA line = UPTREND → Look for BUY signals
  Price BELOW the EMA line = DOWNTREND → Look for SELL signals

  CHART VISUALIZATION:
  
  Price:   ╭──────╮      ╭─────╮
           │      │      │     │      ╭───
           │      ╰──────╯     ╰──────╯
           │     EMA-100 Line
           │
           └──────────────────────────────────► Time

  When price stays above EMA → BUY zone (green)
  When price drops below EMA → SELL zone (red)
```

### 2. Trend Strength Classification

Not all trends are equal. We classify them by how far price has moved from the EMA:

```
TREND STRENGTH VISUALIZATION:
═══════════════════════════════════════════════════════════════════

                    Distance from EMA (in ATR multiples)

    ◄─────────────────────────────────────────────────────────────►
    
    │  WEAK        │  MODERATE      │  STRONG          │
    │  0 - 1 ATR   │  1 - 3 ATR     │  3+ ATR          │
    │              │                │                   │
    │  ░░░░░░░░░░  │  ▒▒▒▒▒▒▒▒▒▒▒  │  ██████████████  │
    │  Light shade │  Medium shade  │  Dark shade      │
    │              │                │                   │
    │  Caution     │  Normal        │  High confidence │
    │              │                │                   │
    
    EMA Line ─────┼────────────────┼───────────────────
                  │                │
               1 ATR            3 ATR
```

**Why this matters:** 
- **Weak trends** (distance < 1 ATR) → Market is choppy, low confidence
- **Moderate trends** (1-3 ATR) → Normal trending, good setups
- **Strong trends** (3+ ATR) → Powerful momentum, highest confidence

### 3. Supply & Demand Zones: Where Big Traders Act

```
DEMAND ZONE (Buyers' Territory):
═══════════════════════════════════════════════════════════════════

    Before the zone forms:
    
    Price:    ╭─╮
              │ │
              │ │  ← Price drops
              │ │
              │ ╰─────╮
                      │
    
    After 4+ bullish candles appear:
    
    Price:    ╭─╮
              │ │
              │ │
              │ ╰─────╮
                      │
    ══════════════════════════════  ← DEMAND ZONE TOP
    │  ░░░░░░░░░░░░░░░░░░░░░░░░  │
    │  ░░ ZONE OF INTEREST ░░░░  │  ← Price may bounce here
    │  ░░░░░░░░░░░░░░░░░░░░░░░░  │
    ══════════════════════════════  ← DEMAND ZONE BOTTOM


SUPPLY ZONE (Sellers' Territory):
═══════════════════════════════════════════════════════════════════

    Before the zone forms:
    
                    ╭─────╮
                    │
    Price:          │
                    │
                    ╰─╮
                      │  ← Price rises
    
    After 4+ bearish candles appear:
    
                    ╭─────╮
                    │
    ════════════════╪══════════════  ← SUPPLY ZONE TOP
    │  ▓▓▓▓▓▓▓▓▓▓▓▓│▓▓▓▓▓▓▓▓▓▓▓▓  │
    │  ▓▓ ZONE OF INTEREST ▓▓▓▓▓  │  ← Price may reject here
    │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │
    ════════════════╪══════════════  ← SUPPLY ZONE BOTTOM
                    │
                    ╰─╮
                      │
```

### 4. Swing Level Breakout: Confirmation Signal

Before entering a trade, we need proof that price is respecting the zone:

```
SWING BREAKOUT LOGIC:
═══════════════════════════════════════════════════════════════════

    For a BUY signal:
    
         ╭─────╮  ← Swing High (RESISTANCE)
         │     │
    ─────┼─────┼─────────────────────────────────────────
         │     │
         │     ╰──╮
         │        │
         │        ╰──╮    ← Price breaks ABOVE swing high
         │           │       (CONFIRMATION!)
         │           ╰──╮
         │              │
         │              ╰──► ENTER BUY
    
    For a SELL signal:
    
         │              ╭──╮
         │              │  │
         │           ╭──╯  │
         │           │     │    ← Price breaks BELOW swing low
         │        ╭──╯     │       (CONFIRMATION!)
         │        │        │
    ─────┼────────┼────────┼─────────────────────────────
         │        │
         ╰─────╯  ← Swing Low (SUPPORT)
```

### 5. Entry, Stop Loss, and Take Profit

```
TRADE SETUP ANATOMY (BUY Example):
═══════════════════════════════════════════════════════════════════

                        🎯 TAKE PROFIT
                        ════════════════════════════════════════
                        │                                    │
                        │        PROFIT ZONE                 │
                        │        (2x your risk)              │
                        │                                    │
                        ════════════════════════════════════════
                        
    ────────────────────────────────────────────────────────────────
                        📍 ENTRY
                        ════════════════════════════════════════
                        │                                    │
                        │        DEMAND ZONE                │
                        │        (where buyers are)         │
                        │                                    │
                        ════════════════════════════════════════
                        
    ────────────────────────────────────────────────────────────────
                        🛑 STOP LOSS
                        ════════════════════════════════════════
                        │                                    │
                        │        RISK ZONE                  │
                        │        (1x risk)                  │
                        │                                    │
                        ════════════════════════════════════════


    RISK/REWARD CALCULATION:
    ────────────────────────────────────────────────────────────────
    
    Risk   = Entry - Stop Loss    = $X
    Reward = Take Profit - Entry  = $2X (always 2x the risk)
    
    If risk is $500 → Reward target is $1,000
    If risk is $1,000 → Reward target is $2,000
```

### 6. Multi-Timeframe Analysis: The Power Combo

```
WHY TWO TIMEFRAMES?
═══════════════════════════════════════════════════════════════════

    ┌─────────────────────────────────────────────────────────────┐
    │  1-HOUR CHART (Big Picture)                                 │
    │  ─────────────────────────────────────────────────────────  │
    │  • Shows the overall TREND direction                        │
    │  • EMA-100 on 1H = reliable trend filter                    │
    │  • ATR on 1H = proper volatility measurement                │
    │                                                             │
    │  Like looking at a MAP before driving                       │
    └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  5-MINUTE CHART (Precision Entry)                           │
    │  ─────────────────────────────────────────────────────────  │
    │  • Shows detailed price action                              │
    │  • Supply/Demand zones detected on 5M                       │
    │  • Swing levels identified on 5M                            │
    │  • Entry trigger fires on 5M                                │
    │                                                             │
    │  Like zooming in on the GPS for exact turns                 │
    └─────────────────────────────────────────────────────────────┘
```

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SYSTEM ARCHITECTURE                               │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │   BINANCE    │     │   STRATEGY   │     │   TELEGRAM   │
    │    API       │────►│    ENGINE    │────►│   NOTIFIER   │
    │              │     │              │     │              │
    │ • 1H Candles │     │ • Indicators │     │ • Signals    │
    │ • 5M Candles │     │ • Zones      │     │ • Updates    │
    │ • Live Price │     │ • Signals    │     │ • Journal    │
    └──────────────┘     └──────────────┘     └──────────────┘
           │                    │                     │
           │                    ▼                     │
           │           ┌──────────────┐              │
           │           │  EXECUTION   │              │
           │           │   MANAGER    │              │
           │           │              │              │
           │           │ • Monitor    │              │
           │           │ • Close      │              │
           │           │ • Journal    │              │
           │           └──────────────┘              │
           │                    │                     │
           │                    ▼                     │
           │           ┌──────────────┐              │
           └──────────►│   STORAGE    │◄─────────────┘
                       │   (JSON)     │
                       │              │
                       │ • Trades     │
                       │ • State      │
                       │ • Journal    │
                       └──────────────┘
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW DIAGRAM                           │
└─────────────────────────────────────────────────────────────────────┘

    BINANCE API                  YOUR BOT                 TELEGRAM
    ──────────                   ────────                 ────────
         │                           │                        │
         │  1. Request 1H candles    │                        │
         │◄──────────────────────────│                        │
         │──────────────────────────►│                        │
         │                           │                        │
         │  2. Request 5M candles    │                        │
         │◄──────────────────────────│                        │
         │──────────────────────────►│                        │
         │                           │                        │
         │  3. Request live price    │                        │
         │◄──────────────────────────│                        │
         │──────────────────────────►│                        │
         │                           │                        │
         │                      ┌────┴────┐                   │
         │                      │ PROCESS │                   │
         │                      │  DATA   │                   │
         │                      └────┬────┘                   │
         │                           │                        │
         │                           │  4. Send Signal        │
         │                           │───────────────────────►│
         │                           │                        │
         │                           │  5. Send Updates       │
         │                           │───────────────────────►│
         │                           │                        │
         │                           │  6. Send Journal       │
         │                           │───────────────────────►│
```

---

## Getting Started

### Prerequisites

```bash
# Python 3.8 or higher
python --version

# Required packages
pip install pandas numpy requests schedule
```

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/DannySol12/nad-btc.git
cd nad-btc

# 2. Install dependencies
pip install pandas numpy requests schedule

# 3. Configure your Telegram bot (see Configuration section)

# 4. Run the bot
python main.py
```

### Quick Start Checklist

```
┌─────────────────────────────────────────────────────────────────────┐
│  ☐ 1. Get a Telegram Bot Token from @BotFather                     │
│  ☐ 2. Get your Chat ID from @userinfobot                          │
│  ☐ 3. Update config.py with your credentials                       │
│  ☐ 4. Install Python dependencies                                  │
│  ☐ 5. Run: python main.py                                          │
│  ☐ 6. Wait for first signal (usually within 5 minutes)             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Configuration

### config.py Settings

```python
# TELEGRAM CREDENTIALS (Required)
TELEGRAM_TOKEN = "your_bot_token_here"  # From @BotFather
CHAT_ID        = "your_chat_id_here"    # From @userinfobot

# TRADING PAIR
SYMBOLS = ["BTC/USD"]  # Currently supports BTC only

# INDICATOR SETTINGS
EMA_PERIOD       = 100    # EMA length for trend detection
ATR_PERIOD       = 14     # ATR length for volatility
MIN_ZONE_CANDLES = 4      # Consecutive candles to form a zone
SWING_LOOKBACK   = 10     # Candles to look back for swing points
ZONE_LOOKBACK    = 50     # How far back to search for zones

# RISK MANAGEMENT
RR_RATIO         = 2.0    # Risk/Reward ratio (always 2:1)
SL_BUFFER_ATR_MULT = 0.2  # Stop loss buffer (0.2x ATR)

# TIMING
MONITOR_INTERVAL = 45     # Check open trades every 45 seconds
SIGNAL_INTERVAL  = 300    # Scan for signals every 5 minutes

# POSITION SIZING
ACCOUNT_SIZE  = 10000     # Your account size in USD
LOT_SIZE      = 1.0       # Trade size
```

### Tuning Parameters

| Parameter | Default | Description | Impact |
|-----------|---------|-------------|--------|
| `EMA_PERIOD` | 100 | EMA smoothing period | Higher = slower trend detection |
| `ATR_PERIOD` | 14 | ATR calculation period | Higher = smoother volatility reading |
| `MIN_ZONE_CANDLES` | 4 | Candles needed for zone | Higher = stronger zones, fewer signals |
| `SWING_LOOKBACK` | 10 | Swing detection window | Higher = more significant swings |
| `RR_RATIO` | 2.0 | Risk/Reward target | Higher = larger winners, lower win rate |

---

## File Structure

```
nad-btc/
├── main.py                          # Entry point - runs the bot
├── config.py                        # All settings in one place
├── storage.py                       # Persistence layer (JSON files)
│
├── data/
│   ├── binance_client.py            # Binance API wrapper
│
├── strategy/
│   ├── indicators.py                # EMA, ATR, Swing detection
│   ├── zones.py                     # Supply/Demand zone detection
│   └── signals.py                   # Signal generation logic
│
├── execution/
│   ├── trade_manager.py             # Monitors open trades
│   └── journal.py                   # Trade logging & daily summary
│
├── notifications/
│   └── telegram.py                  # All Telegram messaging
│
├── backtests/
│   ├── btc_5m_exit_backtest.py      # Backtesting engine
│   └── btc_current_architecture_backtest.py  # Live architecture backtest
│
├── btc_active_trades_v9.json        # Current open trades
├── btc_journal_v9.json              # Trade history
├── btc_signal_state_v9.json         # Signal cooldown state
│
└── .gitignore
```

---

## Backtesting

### Running Backtests

```bash
# Run the backtesting engine
python backtests/btc_5m_exit_backtest.py --days 365

# Run current architecture validation
python backtests/btc_current_architecture_backtest.py --days 730
```

### Backtest Results (Reference)

```
HISTORICAL PERFORMANCE (365-day study):
═══════════════════════════════════════════════════════════════════

    Metric                  Value
    ─────────────────────────────────────────
    Total Trades            ~575
    Win Rate                ~36%
    Expectancy              +0.085R per trade
    
    Note: This is BEFORE trading costs (fees + slippage)
    
COST SENSITIVITY:
    ─────────────────────────────────────────
    No costs:               +0.085R expectancy
    5bps fee + 1bps slip:   +0.079R expectancy
    7.5bps fee + 2.5bps:    +0.076R expectancy
    10bps fee + 5bps slip:  +0.072R expectancy
```

### What is "R"?

```
UNDERSTANDING "R" (Risk Units):
═══════════════════════════════════════════════════════════════════

    R = 1 unit of risk (your stop loss distance)
    
    Example:
    ─────────────────────────────────────────
    Entry:    $50,000
    Stop:     $49,500
    Risk:     $500 (this is 1R)
    
    Take Profit: $51,000 (2R = $1,000)
    
    If you WIN:  You gain +2R (+$1,000)
    If you LOSE: You lose -1R (-$500)
    
    With a 36% win rate and 2:1 reward:risk:
    ─────────────────────────────────────────
    Expected Value = (0.36 × 2R) + (0.64 × -1R)
                   = 0.72R - 0.64R
                   = +0.08R per trade (positive edge!)
```

---

## Risk Disclaimer

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ⚠️  IMPORTANT WARNING                        │
└─────────────────────────────────────────────────────────────────────┘

    This trading bot is for EDUCATIONAL PURPOSES ONLY.
    
    • Trading involves substantial risk of loss
    • Past performance does not guarantee future results
    • You can lose more than your initial investment
    • The bot does NOT guarantee profits
    • Always use proper position sizing
    • Never trade with money you cannot afford to lose
    
    The author is not responsible for any financial losses
    incurred from using this software.
    
    USE AT YOUR OWN RISK.
```

---

## Telegram Notifications

### What You'll Receive

```
SIGNAL ALERT EXAMPLE:
═══════════════════════════════════════════════════════════════════

🟢 BUY 🟢 LONG — BTC/USD 📈
🧭 Trend strength: Strong

📍 Entry:  $50,250.00
🛑 Stop Loss:  $49,800.00
🎯 Take Profit:  $51,150.00
⚖️ Risk/Reward:  1:2.0

📦 1H Zone:  $49,750.00 — $50,200.00
⏰ Time:  2024-01-15 14:30 UTC

⚠️ Verify on chart before entering


UPDATE ALERTS:
═══════════════════════════════════════════════════════════════════

🔒 BREAKEVEN — BTC/USD | BUY 🟢
   Entry: $50,250.00
   Current: $50,500.00
   SL moved to entry: $50,250.00
   ✅ You cannot lose on this trade now

💰 IN PROFIT — BTC/USD | BUY 🟢
   Entry: $50,250.00
   Current: $50,700.00
   TP: $51,150.00 (50% of the way there)

🎯 TAKE PROFIT HIT — BTC/USD | BUY 🟢 ✅
   Entry: $50,250.00
   TP: $51,150.00
   💵 P&L: +$900.00  (+9.00% of account)
   🏆 Winning trade closed!
```

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

## Acknowledgments

- [Binance](https://www.binance.com/) - Public API for market data
- [Telegram](https://core.telegram.org/) - Notification system
- [Python](https://www.python.org/) - Programming language
- [Pandas](https://pandas.pydata.org/) - Data manipulation
- [NumPy](https://numpy.org/) - Numerical computing

---

<div align="center">

**Built with ❤️ for the trading community**

*Remember: The market can remain irrational longer than you can remain solvent.*

</div>