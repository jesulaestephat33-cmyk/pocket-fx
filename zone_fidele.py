# Pocket FX - test du mode "Fidele" de la Zone de Pouvoir 20/200 (SMA20 M5 + SMA200 M30), spread inclus
import math, sys
from orb_ny import ny_off

def run(c, sp, be_on=True):
    n = len(c); cl = [x['close'] for x in c]; s20 = [0.0]*n
    for i in range(19, n): s20[i] = sum(cl[i-19:i+1])/20
    g = {}
    for i, x in enumerate(c): g.setdefault(x['time']//1800, []).append(i)
    m30 = [(k, cl[v[-1]]) for k, v in sorted(g.items()) if len(v) == 6]
    kt = [k for k, _ in m30]; mc = [v for _, v in m30]; s2 = [0.0]*len(mc)
    for i in range(199, len(mc)): s2[i] = sum(mc[i-199:i+1])/200
    ptr = -1; blue = [0.0]*n; bsl = [0.0]*n
    for i in range(n):
        while ptr + 1 < len(kt) and (kt[ptr+1] + 1)*1800 <= c[i]['time'] + 300: ptr += 1
        if ptr >= 201: blue[i] = s2[ptr]; bsl[i] = s2[ptr] - s2[ptr-2]
    out = []; i = 220
    while i < n - 2:
        t = c[i]['time'] + ny_off(c[i]['time']); mod = t % 86400
        if mod < 9*3600 + 1800 or mod >= 15*3600 + 3300 or blue[i] == 0 or s20[i-3] == 0: i += 1; continue
        up = s20[i] > blue[i] and s20[i] > s20[i-3] and bsl[i] > 0; dn = s20[i] < blue[i] and s20[i] < s20[i-3] and bsl[i] < 0
        b = c[i]; s = 0
        if up and b['low'] <= s20[i] and b['close'] > s20[i] and b['close'] > b['open']: s = 1
        if dn and b['high'] >= s20[i] and b['close'] < s20[i] and b['close'] < b['open']: s = -1
        if s == 0: i += 1; continue
        e = b['close']; stop = blue[i]; risk = (e - stop)*s
        if risk <= 0 or abs(e - s20[i]) > 3*risk: i += 1; continue
        cur = stop; day = t // 86400; j = i + 1; res = None
        while j < n:
            tj = c[j]['time'] + ny_off(c[j]['time'])
            if tj // 86400 != day or tj % 86400 >= 15*3600 + 3300: res = (cl[j-1] - e)*s/risk; break
            x = c[j]
            if (x['low'] <= cur if s > 0 else x['high'] >= cur): res = (cur - e)*s/risk; break
            if be_on and cur != e and (x['high'] >= e + risk if s > 0 else x['low'] <= e - risk): cur = e
            j += 1
        if res is None: break
        out.append((i, res - sp/risk)); i = j + 1
    return out

def stat(r):
    n = len(r)
    if n < 2: return "%3d trades" % n
    mu = sum(r)/n; sd = math.sqrt(sum((x-mu)**2 for x in r)/(n-1)) or 1e-9; w = sum(x for x in r if x > 0); l = -sum(x for x in r if x < 0)
    return "%3d trades | gagnants %2d%% | net %+6.1fR moy %+.3fR t %+.2f | PF %.2f" % (n, 100*sum(1 for x in r if x > 0)/n, sum(r), mu, mu/sd*math.sqrt(n), w/l if l else 9.99)

if __name__ == '__main__':
    from backtest3 import load
    d = load(20000, 5); allr = []; a1 = []; a2 = []
    print("\nZONE DE POUVOIR 20/200 (mode Fidele) | M5 | fenetre 09:30-15:55 NY | spread inclus")
    for a, (c, sp) in d.items():
        o = run(c, sp); cut = int(len(c)*0.6); r = [x[1] for x in o]; allr += r
        a1 += [x[1] for x in o if x[0] < cut]; a2 += [x[1] for x in o if x[0] >= cut]
        print("%-8s %s" % (a, stat(r)))
    print("%-8s %s" % ("TOTAL", stat(allr))); print("ancien 60%%: %s" % stat(a1)); print("recent 40%%: %s" % stat(a2))
