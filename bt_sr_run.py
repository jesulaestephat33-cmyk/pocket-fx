# Pocket FX - lance le backtest du moteur Support/Resistance : actuel vs variantes (spread inclus)
import sys, random, math
from bt_sr import BASE, simulate, summ

VARIANTES = [('ACTUEL (ton backend)', {}), ('ACTUEL sans spread (brut)', dict(cost=0)), ('spread <= 20% du risque', dict(spread_max=0.2)),
             ('spread <= 10% du risque', dict(spread_max=0.1)), ('heures 7h-17h UTC', dict(h0=7, h1=17)),
             ('heures 7-17 + spread <= 20%', dict(h0=7, h1=17, spread_max=0.2)), ('TP 8 + spread <= 20%', dict(tp_atr=8.0, spread_max=0.2))]

def fake():
    random.seed(4); N = 16000; t0 = 1700000000 - 1700000000 % 3600; p = 100.0; m1 = []
    for i in range(N):
        d = 0.0009*math.sin(2*math.pi*i/780) + 0.0004*math.sin(2*math.pi*i/2460); o = p; p += d*3 + random.gauss(0, 0.035)
        m1.append({'time':t0+60*i, 'open':o, 'high':max(o, p)+abs(random.gauss(0, .04)), 'low':min(o, p)-abs(random.gauss(0, .04)), 'close':p})
    h1 = [{'time':m1[i]['time'], 'open':m1[i]['open'], 'high':max(x['high'] for x in m1[i:i+60]), 'low':min(x['low'] for x in m1[i:i+60]), 'close':m1[i+59]['close']} for i in range(0, N-59, 60)]
    return {'TEST': (m1, h1, 0.02)}

if __name__ == '__main__':
    nums = [x for x in sys.argv[1:] if x.isdigit()]; N = int(nums[0]) if nums else 50000
    if '--test' in sys.argv: data = fake()
    else:
        from backtest3 import load
        m = load(N, 1); h = load(3000, 60); data = {a:(m[a][0], h[a][0], m[a][1]) for a in m if a in h}
    allres = []
    for name, ov in VARIANTES:
        P = dict(BASE, **ov); tr = []; per = {}
        for a, (m1, h1, sp) in data.items():
            t = simulate(m1, h1, sp, P); per[a] = summ(t); tr += [(a, k, kd, R) for k, kd, R in t]
        tr2 = [(k, kd, R) for _, k, kd, R in tr]; s = summ(tr2); allres.append((name, s, per, tr))
        print(f"{name:26s} {s['n']:5d} signaux | TP {s['tp']:4d} SL {s['sl']:4d} renv {s['rev']:3d} exp {s['exp']:4d} | total {s['R']:+8.1f}R moy {s['mu']:+.3f}R t-stat {s['t']:+.2f}")
    name, s, per, tr = allres[0]
    print('\nPAR ACTIF (reglage ACTUEL) :')
    for a, v in per.items(): print(f"  {a:8s} {v['n']:4d} signaux | TP {v['tp']:3d} SL {v['sl']:3d} | total {v['R']:+7.1f}R")
