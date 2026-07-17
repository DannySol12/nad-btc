"""
data/binance_client.py — Binance public market-data API. No key required.
"""
import requests
import pandas as pd
from config import BINANCE_SYMBOL, BINANCE_INTERVAL


def get_current_price(symbol):
    bn_symbol = BINANCE_SYMBOL.get(symbol, symbol)
    params = {"symbol": bn_symbol}
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price", params=params, timeout=10).json()
        if "price" in r:
            return float(r["price"])
    except:
        pass
    return None


def fetch_candles(symbol, interval, limit=300):
    bn_symbol = BINANCE_SYMBOL.get(symbol, symbol)
    bn_interval = BINANCE_INTERVAL.get(interval, interval)
    params = {"symbol": bn_symbol, "interval": bn_interval, "limit": limit}
    try:
        r = requests.get("https://api.binance.com/api/v3/klines", params=params, timeout=15).json()
        if not isinstance(r, list) or len(r) == 0:
            return None
        # Each row: [openTime, open, high, low, close, volume, closeTime, ...]
        rows = []
        for row in r:
            rows.append({
                'datetime': pd.to_datetime(row[0], unit='ms'),
                'Open': float(row[1]), 'High': float(row[2]),
                'Low': float(row[3]), 'Close': float(row[4])
            })
        df = pd.DataFrame(rows).set_index('datetime').sort_index()
        return df
    except:
        return None
