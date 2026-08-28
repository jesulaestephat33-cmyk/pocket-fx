"""
Pocket FX - backtester
-----------------------------------
Rejoue la stratégie (EMA50 H1 + zones S/R + rejet de bougie M1 + SL/TP)
sur l'historique MT5 réel, sans tricher avec des infos du futur, pour
donner un vrai taux de réussite avant de faire confiance au bot en direct.

Réutilise directement les fonctions de pocket_fx_backend.py (ema, atr,
_cluster_pivots, SYMBOL_MAP) pour garantir que le backtest teste
exactement la même logique que le bot en direct.

Usage :
  python pocket_fx_backtest.py

Ça peut prendre plusieurs minutes la première fois si MT5 doit
télécharger l'historique M1 sur 3 mois pour les 8 actifs.
"""

from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

from pocket_fx_backend import (
    SYMBOL_MAP, ema, atr, _cluster_pivots,
    EMA_PERIOD, ZONE_LOOKBACK, ZONE_TOLERANCE_ATR_MULT,
)

MONTHS = 3
RR_FALLBACK = 2.0


def fetch_range(symbol, timeframe, start, end):
    return mt5.copy_rates_range(symbol, timeframe, start.replace(tzinfo=None), end.replace(tzinfo=None))


def fetch_range_chunked(symbol, timeframe, start, end, chunk_days=7):
    """MT5 refuse parfois les trop grosses requêtes M1 d'un coup (Invalid params) —
    on découpe en morceaux et on recolle."""
    import numpy as np
    chunks = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        part = fetch_range(symbol, timeframe, cursor, chunk_end)
        if part is not None and len(part) > 0:
            chunks.append(part)
        cursor = chunk_end
    if not chunks:
        return None
    return np.concatenate(chunks)


def historical_trend(h1_closes):
    if len(h1_closes) < EMA_PERIOD:
        return None, None
    ema_value = ema(h1_closes[-EMA_PERIOD:], EMA_PERIOD)
    last_close = h1_closes[-1]
    if last_close > ema_value * 1.0005:
        return "up", ema_value
    elif last_close < ema_value * 0.9995:
        return "down", ema_value
    return "flat", ema_value


def check_rejection_from_bar(bar, direction):
    full_range = bar["high"] - bar["low"]
    if full_range <= 0:
        return False
    lower_wick = min(bar["open"], bar["close"]) - bar["low"]
    upper_wick = bar["high"] - max(bar["open"], bar["close"])
    if direction == "up":
        strength = lower_wick / full_range
        return bar["close"] > bar["open"] and strength > 0.4
    else:
        strength = upper_wick / full_range
        return bar["close"] < bar["open"] and strength > 0.4


def run_backtest(symbol, start, end):
    h1_start = start - timedelta(hours=ZONE_LOOKBACK + EMA_PERIOD + 10)
    h1_rates = fetch_range(symbol, mt5.TIMEFRAME_H1, h1_start, end)
    m1_rates = fetch_range_chunked(symbol, mt5.TIMEFRAME_M1, start, end, chunk_days=7)
    h1_count = 0 if h1_rates is None else len(h1_rates)
    m1_count = 0 if m1_rates is None else len(m1_rates)
    print(f"    -> H1 recu: {h1_count} bougies | M1 recu: {m1_count} bougies | erreur MT5: {mt5.last_error()}")
    if h1_rates is None or m1_rates is None or len(h1_rates) < 20 or len(m1_rates) < 10:
        return [], 0

    trades = []
    open_trade = None
    h1_idx = 0
    unresolved = 0

    for m1 in m1_rates:
        t = m1["time"]
        while h1_idx + 1 < len(h1_rates) and h1_rates[h1_idx + 1]["time"] <= t:
            h1_idx += 1
        if h1_idx < EMA_PERIOD:
            continue

        price = m1["close"]

        if open_trade:
            hit_sl = (price <= open_trade["sl"]) if open_trade["dir"] == "up" else (price >= open_trade["sl"])
            hit_tp = (price >= open_trade["tp"]) if open_trade["dir"] == "up" else (price <= open_trade["tp"])
            if hit_sl:   # priorité pessimiste si SL et TP touchés dans la même bougie
                trades.append({**open_trade, "result": "loss", "exit": open_trade["sl"]})
                open_trade = None
            elif hit_tp:
                trades.append({**open_trade, "result": "win", "exit": open_trade["tp"]})
                open_trade = None
            continue

        h1_closes = [h1_rates[i]["close"] for i in range(h1_idx + 1)]
        direction, _ = historical_trend(h1_closes)
        if direction not in ("up", "down"):
            continue

        window_rates = h1_rates[max(0, h1_idx + 1 - ZONE_LOOKBACK):h1_idx + 1]
        if len(window_rates) < 20:
            continue
        clustered, a, tolerance = _cluster_pivots(window_rates, price)

        wanted = "support" if direction == "up" else "resistance"
        candidates = clustered[wanted]
        if not candidates:
            continue
        best = min(candidates, key=lambda c: abs(c["avg"] - price))
        if abs(best["avg"] - price) > tolerance:
            continue

        if not check_rejection_from_bar(m1, direction):
            continue

        buffer = tolerance * 1.2
        target_kind = "resistance" if direction == "up" else "support"
        target_candidates = clustered[target_kind]
        target_candidates = [c for c in target_candidates if (c["avg"] > price if direction == "up" else c["avg"] < price)]
        target = min(target_candidates, key=lambda c: abs(c["avg"] - price)) if target_candidates else None

        if direction == "up":
            sl = best["avg"] - buffer
            tp = target["avg"] if target else price + (price - sl) * RR_FALLBACK
        else:
            sl = best["avg"] + buffer
            tp = target["avg"] if target else price - (sl - price) * RR_FALLBACK

        open_trade = {"dir": direction, "entry": price, "sl": round(sl, 2), "tp": round(tp, 2)}

    if open_trade:
        unresolved = 1

    return trades, unresolved


def summarize(all_trades):
    wins = [t for t in all_trades if t["result"] == "win"]
    total = len(all_trades)
    win_rate = (len(wins) / total * 100) if total else 0

    running, peak, max_dd = 0, 0, 0
    r_values = []
    for t in all_trades:
        risk = abs(t["entry"] - t["sl"])
        reward = abs(t["exit"] - t["entry"])
        r = (reward / risk) if t["result"] == "win" else -1.0
        r_values.append(r)
        running += r
        peak = max(peak, running)
        max_dd = min(max_dd, running - peak)

    avg_r = sum(r_values) / len(r_values) if r_values else 0
    return {"total": total, "wins": len(wins), "losses": total - len(wins),
            "win_rate": round(win_rate, 1), "avg_r": round(avg_r, 2), "max_drawdown_r": round(max_dd, 2)}


def main():
    if not mt5.initialize():
        print("Échec de connexion à MT5 :", mt5.last_error())
        return

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30 * MONTHS)

    combined = []
    total_unresolved = 0
    print(f"Backtest sur {MONTHS} mois ({start.date()} -> {end.date()})\n")

    for asset_id, symbol in SYMBOL_MAP.items():
        info = mt5.symbol_info(symbol)
        if info is None:
            print(f"{asset_id:8s} | symbole introuvable, skip")
            continue
        if not info.visible:
            mt5.symbol_select(symbol, True)

        print(f"{asset_id:8s} | téléchargement / calcul en cours...")
        trades, unresolved = run_backtest(symbol, start, end)
        total_unresolved += unresolved

        if not trades:
            print(f"{asset_id:8s} | aucun trade détecté sur la période")
            continue

        stats = summarize(trades)
        combined.extend(trades)
        print(f"{asset_id:8s} | trades: {stats['total']:4d} | win rate: {stats['win_rate']:5.1f}% "
              f"| R moyen: {stats['avg_r']:+.2f} | drawdown max: {stats['max_drawdown_r']:.2f}R")

    print("\n--- TOTAL COMBINÉ (8 actifs, 3 mois) ---")
    stats = summarize(combined)
    print(f"Trades résolus : {stats['total']} (+ {total_unresolved} encore ouverts en fin de période, exclus)")
    print(f"Win rate       : {stats['win_rate']}%")
    print(f"R moyen/trade  : {stats['avg_r']:+.2f}")
    print(f"Drawdown max   : {stats['max_drawdown_r']:.2f}R")

    mt5.shutdown()


if __name__ == "__main__":
    main()
