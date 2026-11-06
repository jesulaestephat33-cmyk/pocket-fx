# Pocket FX - backtest 3 : cassure/pullback avec stop suiveur, par heure, M15 et H1. Choix sur 60% ancien, verif sur 40% recent
import sys, random
SYMS = {'GER40':'DE30m','CAC40':'FR40m','SPX500':'US500m','NAS100':'USTECm','US30':'US30m','XAUUSD':'XAUUSDm','USOIL':'USOILm','BTCUSD':'BTCUSDm'}

def load(n, tf):
    import MetaTrader5 as mt5
    T = {15: mt5.TIMEFRAME_M15, 60: mt5.TIMEFRAME_H1}[tf]; mt5.initialize(); d = {}
    for a, s in SYMS.items():
        mt5.symbol_select(s, True); r = mt5.copy_rates_from_pos(s, T, 0, n); info = mt5.symbol_info(s)
        if r is None or info is None: continue
        d[a] = ([{'time':int(x['time']), 'open':float(x['open']), 'high':float(x['high']), 'low':float(x['low']), 'close':float(x['close'])} for x in r], info.spread*info.point)
    return d

def fake(n):
    random.seed(5); p = 100.0; c = []; d = 0
    for i in range(n):
        if i % 300 == 0: d = random.choice([-0.03, 0, 0.03])
        o = p; p += d + random.gauss(0, 0.3)
        c.append({'time':1700000000+3600*i, 'open':o, 'high':max(o,p)+abs(random.gauss(0,0.1)), 'low':min(o,p)-abs(random.gauss(0,0.1)), 'close':p})
    return c

def indic(c):
    n = len(c); cl = [x['close'] for x in c]; atr = [0]*n; e20 = [0]*n; e50 = [0]*n; rsi = [50]*n; ch = {20:([0]*n, [0]*n), 55:([0]*n, [0]*n)}; g = l = 0
    for i in range(n):
        e20[i] = cl[i] if i == 0 else cl[i]*2/21 + e20[i-1]*19/21; e50[i] = cl[i] if i == 0 else cl[i]*2/51 + e50[i-1]*49/51
        if i >= 1:
            d = cl[i]-cl[i-1]
            if i <= 14: g += max(d, 0)/14; l += max(-d, 0)/14
            else: g = (g*13+max(d, 0))/14; l = (l*13+max(-d, 0))/14
            rsi[i] = 100 if l == 0 else 100-100/(1+g/l)
        if i >= 14: atr[i] = sum(c[j]['high']-c[j]['low'] for j in range(i-13, i+1))/14
        for N in (20, 55):
            if i >= N: ch[N][0][i] = max(x['high'] for x in c[i-N:i]); ch[N][1][i] = min(x['low'] for x in c[i-N:i])
    return atr, e20, e50, rsi, ch

def trades(c, I, kind, m, hrs, spread, maxhold=100):
    atr, e20, e50, rsi, ch = I; out = []; i = 60; n = len(c)
    while i < n-1:
        a = atr[i]; px = c[i]['close']; side = None; h = (c[i]['time']//3600) % 24
        if a > 0 and hrs[0] <= h < hrs[1]:
            if kind[:3] == 'DON': N = int(kind[3:]); side = 'BUY' if px > ch[N][0][i] else 'SELL' if px < ch[N][1][i] else None
            else:
                if e20[i] > e50[i] and px > e50[i] and rsi[i-1] < 40 and px > c[i-1]['high']: side = 'BUY'
                elif e20[i] < e50[i] and px < e50[i] and rsi[i-1] > 60 and px < c[i-1]['low']: side = 'SELL'
        if not side: i += 1; continue
        s = 1 if side == 'BUY' else -1; risk = m*a; stop = px-s*risk; peak = px; ex = px; j = i
        for j in range(i+1, min(n-1, i+maxhold)+1):
            if s*(c[j]['low' if s > 0 else 'high']-stop) <= 0: ex = stop if s*(c[j]['open']-stop) > 0 else c[j]['open']; break
            peak = max(peak, c[j]['close']) if s > 0 else min(peak, c[j]['close']); ex = c[j]['close']
            if atr[j] > 0: stop = max(stop, peak-m*atr[j]) if s > 0 else min(stop, peak+m*atr[j])
        out.append((i, (ex-px)*s/risk - spread/risk)); i = j+1
    return out

if __name__ == '__main__':
    nums = [x for x in sys.argv[1:] if x.isdigit()]; N = int(nums[0]) if nums else 20000; TF = int(nums[1]) if len(nums) > 1 else 60
    data = {'TEST':(fake(8000), 0.05)} if '--test' in sys.argv else load(N, TF)
    P = {a:(c, indic(c), sp) for a, (c, sp) in data.items()}; res = []
    for kind in ('DON20', 'DON55', 'PB'):
        for m in (2.0, 3.0):
            for hn, hrs in (('toute la journee', (0, 24)), ('Europe 7-12h', (7, 12)), ('US 13-20h', (13, 20))):
                tr, te = [], []
                for a, (c, I, sp) in P.items():
                    cut = int(len(c)*0.6)
                    for i, R in trades(c, I, kind, m, hrs, sp): (tr if i < cut else te).append(R)
                f = lambda L: (len(L), sum(L), sum(x for x in L if x > 0)/max(1e-9, -sum(x for x in L if x < 0)))
                res.append((f(tr), f(te), kind, m, hn))
    res.sort(key=lambda x: -x[0][1])
    print(f'\nTF {TF} min - stop suiveur, spread inclus. APPRENTISSAGE (60% ancien) puis TEST (40% recent, jamais vu)')
    for (n1, R1, pf1), (n2, R2, pf2), kind, m, hn in res:
        ok = '  <== POSITIF PARTOUT' if R1 > 0 and R2 > 0 and n2 >= 100 else ''
        print(f"{kind:5s} stop {m}ATR {hn:17s}| appr {n1:5d} tr {R1:+7.1f}R PF {pf1:4.2f} | TEST {n2:5d} tr {R2:+7.1f}R PF {pf2:4.2f}{ok}")
