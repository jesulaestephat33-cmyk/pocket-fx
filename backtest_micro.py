# Pocket FX - backtest du Micro scalp sur l'historique M1 de MT5 (spread inclus)
import sys, itertools, random
SYMS = {'GER40':'DE30m','CAC40':'FR40m','SPX500':'US500m','NAS100':'USTECm','US30':'US30m','XAUUSD':'XAUUSDm','USOIL':'USOILm','BTCUSD':'BTCUSDm'}

def prep(c):
    n = len(c); e20 = [0]*n; e50 = [0]*n; atr = [0]*n
    k20, k50 = 2/21, 2/51
    for i in range(n):
        p = c[i]['close']
        e20[i] = p if i == 0 else p*k20 + e20[i-1]*(1-k20)
        e50[i] = p if i == 0 else p*k50 + e50[i-1]*(1-k50)
        if i >= 14: atr[i] = sum(c[j]['high']-c[j]['low'] for j in range(i-13, i+1))/14
    return e20, e50, atr

def signal(c, i, E, P):
    e20, e50, atr = E; a = atr[i]
    if i < 70 or a <= 0 or c[i]['time'] - c[i-60]['time'] > 4200*P.get('tf', 1): return None
    px = c[i]['close']; prev = c[i-1]
    for side in ('BUY', 'SELL'):
        s = 1 if side == 'BUY' else -1
        if s*(e20[i]-e50[i]) < P['gap']*a: continue
        win = c[i-19:i+1]
        sw = max(x['high'] for x in win) if s > 0 else min(x['low'] for x in win)
        ext, ei = None, None
        for j in range(i-6, i+1):
            v = c[j]['low'] if s > 0 else c[j]['high']
            if ext is None or s*(v-ext) < 0: ext, ei = v, j
        if s*(sw-ext) < P['depth']*a: continue
        if s*(ext-e50[ei]) < -0.2*a: continue
        if s > 0 and not (px > prev['high'] and px > e20[i]): continue
        if s < 0 and not (px < prev['low'] and px < e20[i]): continue
        sl = min(ext-0.25*a, px-a) if s > 0 else max(ext+0.25*a, px+a)
        risk = abs(px-sl)
        if risk > 3*a or risk <= 0: continue
        return side, px, sl, px + s*P['rr']*risk, risk
    return None

def run(c, E, P, spread):
    out = []; i = 70; n = len(c)
    while i < n-1:
        sg = signal(c, i, E, P)
        if not sg: i += 1; continue
        side, entry, sl, tp, risk = sg; s = 1 if side == 'BUY' else -1
        res, end = 'exp', min(n-1, i+P['hold'])
        for j in range(i+1, end+1):
            hs = c[j]['low'] <= sl if s > 0 else c[j]['high'] >= sl
            ht = c[j]['high'] >= tp if s > 0 else c[j]['low'] <= tp
            if hs: res = 'loss'; break
            if ht: res = 'win'; break
        cost = spread/risk
        r = P['rr']-cost if res == 'win' else (-1-cost if res == 'loss' else 0)
        out.append((res, r)); i = j+1 if res != 'exp' else end+1
    return out

def summary(rows):
    w = sum(1 for x in rows if x[0] == 'win'); l = sum(1 for x in rows if x[0] == 'loss')
    return len(rows), w, l, sum(x[1] for x in rows)

def load(n, tf=1):
    import MetaTrader5 as mt5
    mt5.initialize(); data = {}
    for a, s in SYMS.items():
        mt5.symbol_select(s, True)
        r = mt5.copy_rates_from_pos(s, {1: mt5.TIMEFRAME_M1, 5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15}[tf], 0, n); info = mt5.symbol_info(s)
        if r is None or info is None: continue
        c = [{'time':int(x['time']), 'open':float(x['open']), 'high':float(x['high']), 'low':float(x['low']), 'close':float(x['close'])} for x in r]
        data[a] = (c, info.spread*info.point)
    return data

def fake(n):
    random.seed(3); p = 100.0; c = []; t = 1700000000; d = 0
    for i in range(n):
        if i % 200 == 0: d = random.choice([-0.02, 0, 0.02])
        o = p; p += d + random.gauss(0, 0.08)
        c.append({'time':t+60*i, 'open':o, 'high':max(o,p)+abs(random.gauss(0,0.03)), 'low':min(o,p)-abs(random.gauss(0,0.03)), 'close':p})
    return c

if __name__ == '__main__':
    nums = [x for x in sys.argv[1:] if x.isdigit()]; n = int(nums[0]) if nums else 20000; TF = int(nums[1]) if len(nums) > 1 else 1
    data = {'TEST':(fake(8000), 0.02)} if '--test' in sys.argv else load(n, TF)
    prepd = {a:(c, prep(c), sp) for a, (c, sp) in data.items()}
    grid = [dict(gap=g, depth=d, rr=r, hold=h) for g in (0.25, 0.5) for d in (0.8, 1.2) for r in (1.0, 1.5, 2.0) for h in {1: (15, 30), 5: (6, 12), 15: (4, 8)}[TF]]
    for P in grid: P['tf'] = TF
    res = []
    for P in grid:
        rows = []
        for a, (c, E, sp) in prepd.items(): rows += run(c, E, P, sp)
        res.append((summary(rows), P))
    res.sort(key=lambda x: -x[0][3])
    print('\nMEILLEURS REGLAGES (R net, spread inclus)')
    for (nn, w, l, R), P in res[:6]:
        print(f"{nn:4d} trades  WIN {w:3d}  LOSS {l:3d}  reussite {w/max(1,w+l)*100:4.1f}%  total {R:+7.1f}R  moy {R/max(1,nn):+.3f}R  {P}")
    print('TOTAL meilleur reglage :', f'{res[0][0][3]:+.1f}R sur {res[0][0][0]} trades (TF M{TF})')
    best = res[0][1]
    print('\nPAR ACTIF avec le meilleur reglage', best)
    for a, (c, E, sp) in prepd.items():
        nn, w, l, R = summary(run(c, E, best, sp))
        print(f"{a:8s} {nn:4d} trades  WIN {w:3d}  LOSS {l:3d}  total {R:+7.1f}R")
