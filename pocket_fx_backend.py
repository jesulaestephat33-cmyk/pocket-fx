"""
Pocket FX - moteur de signaux local
-------------------------------------------------
Se connecte au terminal MT5 (Exness) ouvert sur ta machine,
calcule EMA (tendance) + support/résistance + rejet de bougie
pour chaque actif, et expose le résultat en JSON sur
http://localhost:8000

États possibles renvoyés par /api/signal :
  wait          -> rien d'intéressant en ce moment
  approach_buy  -> le prix approche un support en tendance haussière (surveiller BUY)
  approach_sell -> le prix approche une résistance en tendance baissière (surveiller SELL)
  buy / sell    -> entrée confirmée (rejet de bougie sur la zone)
  close         -> la tendance H1 s'est inversée, sortir de la position

Pour relancer à chaque session :
  - Ouvre MT5, connecte-toi
  - cd /c/Pocketfx
  - python pocket_fx_backend.py
  - Laisse ce terminal ouvert, ouvre/recharge pocket-fx.html
"""

import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import MetaTrader5 as mt5

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

SYMBOL_MAP = {
    "GER40":  "DE30m",
    "CAC40":  "FR40m",
    "SPX500": "US500m",
    "NAS100": "USTECm",
    "US30":   "US30m",
    "XAUUSD": "XAUUSDm",
    "USOIL":  "USOILm",
    "BTCUSD": "BTCUSDm",
}

EMA_PERIOD = 50
TREND_TIMEFRAME = mt5.TIMEFRAME_H1
ZONE_TIMEFRAME = mt5.TIMEFRAME_H1
ZONE_LOOKBACK = 150
ENTRY_TIMEFRAME = mt5.TIMEFRAME_M1
ZONE_TOLERANCE_ATR_MULT = 0.5     # distance pour dire "le prix EST sur la zone" (entrée)
APPROACH_ATR_MULT = 1.5           # distance pour dire "le prix APPROCHE la zone" (alerte anticipée)
ZONE_DISPLAY_MAX_ATR_MULT = 20    # au-delà, une zone est trop loin pour être affichée sur le graphique
POLL_SECONDS = 5

TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}

ZONE_WORD = {"up": "support", "down": "résistance"}
ACTION_WORD = {"up": "BUY", "down": "SELL"}

# ------------------------------------------------------------------
# État partagé
# ------------------------------------------------------------------

latest_signals = {aid: {"state": "wait", "confidence": 0, "level": None,
                         "updated_at": None} for aid in SYMBOL_MAP}
position_direction = {aid: None for aid in SYMBOL_MAP}   # 'buy' | 'sell' | None
last_signal_data = {aid: None for aid in SYMBOL_MAP}
lock = threading.Lock()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------
# Analyse technique
# ------------------------------------------------------------------

def ema(values, period):
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def get_trend(symbol):
    rates = mt5.copy_rates_from_pos(symbol, TREND_TIMEFRAME, 0, EMA_PERIOD + 5)
    if rates is None or len(rates) < EMA_PERIOD:
        return None, None
    closes = [r["close"] for r in rates]
    ema_value = ema(closes[-EMA_PERIOD:], EMA_PERIOD)
    last_close = closes[-1]
    if last_close > ema_value * 1.0005:
        return "up", ema_value
    elif last_close < ema_value * 0.9995:
        return "down", ema_value
    return "flat", ema_value


def atr(rates, period=14):
    trs = []
    for i in range(1, len(rates)):
        h, l, pc = rates[i]["high"], rates[i]["low"], rates[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return 0
    return sum(trs[-period:]) / min(period, len(trs))


def _cluster_pivots(rates, current_price, window=3):
    pivots = []
    for i in range(window, len(rates) - window):
        highs = [rates[j]["high"] for j in range(i - window, i + window + 1)]
        lows = [rates[j]["low"] for j in range(i - window, i + window + 1)]
        if rates[i]["high"] == max(highs):
            pivots.append(("resistance", rates[i]["high"]))
        if rates[i]["low"] == min(lows):
            pivots.append(("support", rates[i]["low"]))

    a = atr(rates)
    tolerance = max(a * ZONE_TOLERANCE_ATR_MULT, current_price * 0.0005)

    result = {"support": [], "resistance": []}
    for kind in ("support", "resistance"):
        candidates = sorted([lvl for k, lvl in pivots if k == kind])
        clusters = []
        for lvl in candidates:
            placed = False
            for cl in clusters:
                if abs(lvl - cl["avg"]) <= tolerance:
                    cl["levels"].append(lvl)
                    cl["avg"] = sum(cl["levels"]) / len(cl["levels"])
                    placed = True
                    break
            if not placed:
                clusters.append({"levels": [lvl], "avg": lvl})
        result[kind] = clusters
    return result, a, tolerance


def nearest_zone(symbol, direction, current_price):
    """Zone la plus proche du côté pertinent (support si tendance up, résistance si down),
    avec sa distance au prix actuel."""
    rates = mt5.copy_rates_from_pos(symbol, ZONE_TIMEFRAME, 0, ZONE_LOOKBACK)
    if rates is None or len(rates) < 20:
        return None

    clustered, a, tolerance = _cluster_pivots(rates, current_price)
    wanted = "support" if direction == "up" else "resistance"
    clusters = clustered[wanted]
    if not clusters:
        return None

    best = min(clusters, key=lambda c: abs(c["avg"] - current_price))
    return {
        "level": best["avg"],
        "touches": len(best["levels"]),
        "distance": abs(best["avg"] - current_price),
        "tolerance": tolerance,
    }


def find_target_zone(symbol, direction, current_price):
    """Prochaine zone opposée au-delà du prix, dans le sens du trade (pour le take profit)."""
    rates = mt5.copy_rates_from_pos(symbol, ZONE_TIMEFRAME, 0, ZONE_LOOKBACK)
    if rates is None or len(rates) < 20:
        return None
    clustered, a, tolerance = _cluster_pivots(rates, current_price)
    wanted = "resistance" if direction == "up" else "support"
    candidates = clustered[wanted]
    if direction == "up":
        candidates = [c for c in candidates if c["avg"] > current_price]
    else:
        candidates = [c for c in candidates if c["avg"] < current_price]
    if not candidates:
        return None
    best = min(candidates, key=lambda c: abs(c["avg"] - current_price))
    return {"level": best["avg"], "touches": len(best["levels"])}


def all_zones(symbol, max_per_side=3):
    """Toutes les zones support/résistance pertinentes, pour affichage sur le graphique."""
    rates = mt5.copy_rates_from_pos(symbol, ZONE_TIMEFRAME, 0, ZONE_LOOKBACK)
    if rates is None or len(rates) < 20:
        return []

    tick = mt5.symbol_info_tick(symbol)
    current_price = tick.bid if tick else rates[-1]["close"]

    clustered, a, _ = _cluster_pivots(rates, current_price)
    max_distance = a * ZONE_DISPLAY_MAX_ATR_MULT

    MIN_TOUCHES = 2
    zones = []
    for kind in ("support", "resistance"):
        clusters = [c for c in clustered[kind] if abs(c["avg"] - current_price) <= max_distance]
        respected = [c for c in clusters if len(c["levels"]) >= MIN_TOUCHES]
        pool = respected if respected else clusters
        pool.sort(key=lambda c: abs(c["avg"] - current_price))
        for c in pool[:max_per_side]:
            zones.append({"type": kind, "price": round(c["avg"], 2), "touches": len(c["levels"])})
    return zones


def check_rejection(symbol, direction):
    rates = mt5.copy_rates_from_pos(symbol, ENTRY_TIMEFRAME, 0, 5)
    if rates is None or len(rates) < 2:
        return False, 0

    last = rates[-1]
    full_range = last["high"] - last["low"]
    if full_range <= 0:
        return False, 0

    lower_wick = min(last["open"], last["close"]) - last["low"]
    upper_wick = last["high"] - max(last["open"], last["close"])

    if direction == "up":
        strength = lower_wick / full_range
        confirmed = last["close"] > last["open"] and strength > 0.4
    else:
        strength = upper_wick / full_range
        confirmed = last["close"] < last["open"] and strength > 0.4

    return confirmed, round(min(strength, 1.0) * 100)


def check_zone_rejection(symbol, direction, zone_level, tolerance, lookback=5):
    """Scanne les 5 dernières bougies M1 (pas juste la toute dernière) pour voir
    si l'une d'elles a touché la zone avec un vrai rejet — évite de rater un signal
    entre deux cycles de vérification (5s)."""
    rates = mt5.copy_rates_from_pos(symbol, ENTRY_TIMEFRAME, 0, lookback)
    if rates is None or len(rates) < 1:
        return False, 0

    for bar in rates[::-1]:
        if direction == "up":
            touched = zone_level - tolerance * 3 <= bar["low"] <= zone_level + tolerance
        else:
            touched = zone_level - tolerance <= bar["high"] <= zone_level + tolerance * 3
        if not touched:
            continue

        full_range = bar["high"] - bar["low"]
        if full_range <= 0:
            continue
        lower_wick = min(bar["open"], bar["close"]) - bar["low"]
        upper_wick = bar["high"] - max(bar["open"], bar["close"])

        if direction == "up":
            strength = lower_wick / full_range
            if bar["close"] > bar["open"] and strength > 0.4:
                return True, round(min(strength, 1.0) * 100)
        else:
            strength = upper_wick / full_range
            if bar["close"] < bar["open"] and strength > 0.4:
                return True, round(min(strength, 1.0) * 100)

    return False, 0


def compute_signal(asset_id, symbol):
    info = mt5.symbol_info(symbol)
    if info is None:
        return {"state": "wait", "confidence": 0, "level": None, "updated_at": now_iso(),
                "error": f"symbole '{symbol}' inconnu de MT5 (vérifie le nom exact)"}
    if not info.visible:
        mt5.symbol_select(symbol, True)
        time.sleep(0.3)

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"state": "wait", "confidence": 0, "level": None, "updated_at": now_iso(),
                "error": "symbole introuvable"}

    price = tick.bid
    direction, ema_val = get_trend(symbol)

    if direction in (None, "flat"):
        position_direction[asset_id] = None
        last_signal_data[asset_id] = None
        return {"state": "wait", "confidence": 0, "level": None, "updated_at": now_iso()}

    # CLOSE NOW : la tendance H1 s'est inversée par rapport à la position tenue
    if position_direction[asset_id] == "buy" and direction == "down":
        position_direction[asset_id] = None
        last_signal_data[asset_id] = None
        return {"state": "close", "confidence": 80, "level": round(ema_val, 2),
                "message": f"{asset_id} : tendance inversée — CLOSE la position", "updated_at": now_iso()}
    if position_direction[asset_id] == "sell" and direction == "up":
        position_direction[asset_id] = None
        last_signal_data[asset_id] = None
        return {"state": "close", "confidence": 80, "level": round(ema_val, 2),
                "message": f"{asset_id} : tendance inversée — CLOSE la position", "updated_at": now_iso()}

    # HOLD : un signal buy/sell déjà émis reste affiché tant que la tendance ne s'est pas inversée
    expected = "buy" if direction == "up" else "sell"
    if position_direction[asset_id] == expected and last_signal_data[asset_id]:
        held = last_signal_data[asset_id]
        sl, tp = held.get("sl"), held.get("tp")
        hit = None
        if sl is not None and tp is not None:
            if direction == "up":
                if price >= tp: hit = "tp"
                elif price <= sl: hit = "sl"
            else:
                if price <= tp: hit = "tp"
                elif price >= sl: hit = "sl"
        if hit:
            position_direction[asset_id] = None
            last_signal_data[asset_id] = None
            COOLDOWN[asset_id] = time.time() + 300
            label = "Take profit atteint" if hit == "tp" else "Stop loss touché"
            return {"state": "close", "confidence": 90, "level": round(price, 2),
                    "message": f"{asset_id} : {label} — CLOSE la position", "updated_at": now_iso()}
        out = dict(held)
        out["updated_at"] = now_iso()
        return out

    if time.time() < COOLDOWN.get(asset_id, 0):
        return {"state": "wait", "confidence": 0, "level": None, "message": f"{asset_id} : pause après la fin du dernier signal", "updated_at": now_iso()}

    zone = nearest_zone(symbol, direction, price)
    if zone is None:
        return {"state": "wait", "confidence": 0, "level": None, "updated_at": now_iso()}

    zone_word = ZONE_WORD[direction]
    action = ACTION_WORD[direction]
    level_r = round(zone["level"], 2)

    # 1) On scanne d'abord les 5 dernières bougies M1 pour un rejet sur la zone,
    #    peu importe si le prix actuel s'est déjà un peu éloigné entre-temps
    rejected, wick_strength = check_zone_rejection(symbol, direction, zone["level"], zone["tolerance"])
    if rejected:
        confidence = min(50 + zone["touches"] * 8 + wick_strength // 4, 97)
        state = "buy" if direction == "up" else "sell"
        position_direction[asset_id] = state

        buffer = zone["tolerance"] * 1.2
        target = find_target_zone(symbol, direction, price)
        MIN_REWARD_MULT = 1.5
        if direction == "up":
            sl = round(zone["level"] - buffer, 2)
            risk = price - sl
            fallback_tp = round(price + risk * 2, 2)
            tp = round(target["level"], 2) if (target and (target["level"] - price) >= risk * MIN_REWARD_MULT) else fallback_tp
        else:
            sl = round(zone["level"] + buffer, 2)
            risk = sl - price
            fallback_tp = round(price - risk * 2, 2)
            tp = round(target["level"], 2) if (target and (price - target["level"]) >= risk * MIN_REWARD_MULT) else fallback_tp

        if risk <= 0 or risk < max(zone["tolerance"] * 0.5, price * 0.0002):
            position_direction[asset_id] = None
            return {"state": "wait", "confidence": 15, "level": level_r,
                    "message": f"{asset_id} : signal ignoré (prix déjà au-delà de la zone ou SL trop proche)", "updated_at": now_iso()}

        result = {
            "state": state, "confidence": confidence, "level": level_r,
            "price_exness": round(price, 2), "sl": sl, "tp": tp,
            "message": f"{asset_id} confirme {action} sur {zone_word} {level_r} · SL {sl} · TP {tp}",
            "signal_time": int(time.time()),
            "updated_at": now_iso(),
        }
        last_signal_data[asset_id] = result
        return result

    # 2) Pas de rejet trouvé -> message selon la distance actuelle
    if zone["distance"] <= zone["tolerance"]:
        return {
            "state": "wait", "confidence": min(30 + zone["touches"] * 10, 60), "level": level_r,
            "message": f"{asset_id} est sur {zone_word} {level_r} — en attente de confirmation",
            "updated_at": now_iso(),
        }

    if zone["distance"] <= zone["tolerance"] * APPROACH_ATR_MULT:
        confidence = min(25 + zone["touches"] * 8, 55)
        return {
            "state": f"approach_{'buy' if direction == 'up' else 'sell'}",
            "confidence": confidence, "level": level_r,
            "message": f"{asset_id} approche {zone_word} {level_r} — possibilité de {action}",
            "updated_at": now_iso(),
        }

    return {"state": "wait", "confidence": 15, "level": level_r, "updated_at": now_iso()}


# ------------------------------------------------------------------
# Boucle d'analyse en arrière-plan
# ------------------------------------------------------------------

COOLDOWN = {}


def analysis_loop():
    while True:
        for asset_id, symbol in SYMBOL_MAP.items():
            try:
                result = compute_signal(asset_id, symbol)
                with lock:
                    latest_signals[asset_id] = result
            except Exception as e:
                with lock:
                    latest_signals[asset_id] = {"state": "wait", "confidence": 0, "level": None,
                                                 "error": str(e), "updated_at": now_iso()}
        time.sleep(POLL_SECONDS)


# ------------------------------------------------------------------
# Serveur HTTP local
# ------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/api/signal":
            asset_id = qs.get("asset", [None])[0]
            with lock:
                data = latest_signals.get(asset_id, {"error": "actif inconnu"})
            self._json(data)

        elif parsed.path == "/api/symbols":
            query = qs.get("q", [""])[0].upper()
            all_symbols = mt5.symbols_get()
            names = [s.name for s in all_symbols] if all_symbols else []
            if query:
                names = [n for n in names if query in n.upper()]
            self._json({"count": len(names), "symbols": names[:200]})

        elif parsed.path == "/api/candles":
            asset_id = qs.get("asset", [None])[0]
            tf = qs.get("tf", ["M5"])[0]
            count = min(int(qs.get("count", ["300"])[0]), 20000)
            symbol = SYMBOL_MAP.get(asset_id)
            data = []
            if symbol:
                info = mt5.symbol_info(symbol)
                if info and not info.visible:
                    mt5.symbol_select(symbol, True)
                rates = mt5.copy_rates_from_pos(symbol, TF_MAP.get(tf, mt5.TIMEFRAME_M5), 0, count)
                tick = mt5.symbol_info_tick(symbol)
                broker_offset = int(tick.time - time.time()) if tick else 0
                if rates is not None:
                    data = [{"time": int(r["time"]) - broker_offset, "open": float(r["open"]), "high": float(r["high"]),
                             "low": float(r["low"]), "close": float(r["close"])} for r in rates]
            self._json(data)

        elif parsed.path == "/api/levels":
            asset_id = qs.get("asset", [None])[0]
            symbol = SYMBOL_MAP.get(asset_id)
            zones = all_zones(symbol) if symbol else []
            if symbol:
                direction, _ = get_trend(symbol)
                tick = mt5.symbol_info_tick(symbol)
                if direction in ("up", "down") and tick:
                    active = nearest_zone(symbol, direction, tick.bid)
                    if active:
                        matched = False
                        for z in zones:
                            if abs(z["price"] - active["level"]) < 0.01:
                                z["active"] = True
                                matched = True
                        if not matched:
                            zones.append({
                                "type": "support" if direction == "up" else "resistance",
                                "price": round(active["level"], 2),
                                "touches": active["touches"],
                                "active": True,
                            })
            self._json({"zones": zones})

        else:
            self.send_response(404)
            self.end_headers()


def main():
    if not mt5.initialize():
        print("Échec de connexion à MT5 :", mt5.last_error())
        return
    print("Connecté à MT5. Démarrage de l'analyse...")

    threading.Thread(target=analysis_loop, daemon=True).start()

    server = ThreadingHTTPServer(("localhost", 8000), Handler)
    print("Backend actif sur http://localhost:8000/api/signal?asset=NAS100")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
