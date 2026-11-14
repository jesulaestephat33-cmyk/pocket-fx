# Pocket FX - test des 5 moteurs journaliers (RSI2, Double 7, Fin de mois, Tendance 12 mois, IBS), long seulement, au-dessus SMA200 J
import math, sys, datetime as dt

def sma(x, n, i): return sum(x[i-n+1:i+1])/n if i >= n-1 else None

def engines(d):
    n = len(d); c = [x['close'] for x in d]; h = [x['high'] for x in d]; l = [x['low'] for x in d]
    mo = [dt.datetime.fromtimestamp(x['time'], dt.timezone.utc).month for x in d]
    P = {k: [0]*n for k in ('RSI2', 'DOUBLE7', 'FIN MOIS', 'TENDANCE12', 'IBS')}
    g = lo = 0.0; st = {'RSI2': 0, 'DOUBLE7': 0, 'IBS': 0}; eom_until = -1
    for i in range(1, n):
        dd = c[i]-c[i-1]
        if i <= 2: g += max(dd, 0)/2; lo += max(-dd, 0)/2
        else: g = (g+max(dd, 0))/2; lo = (lo+max(-dd, 0))/2
        r2 = 100 if lo == 0 else 100-100/(1+g/lo)
        s200 = sma(c, 200, i)
        if s200 is None or i < 252: continue
        up = c[i] > s200; s5 = sma(c, 5, i); w = c[i-6:i+1]; ibs = (c[i]-l[i])/(h[i]-l[i]) if h[i] > l[i] else 0.5
        if st['RSI2']: st['RSI2'] = 0 if c[i] > s5 else 1
        elif r2 < 10 and up: st['RSI2'] = 1
        if st['DOUBLE7']: st['DOUBLE7'] = 0 if c[i] >= max(w) else 1
        elif c[i] <= min(w) and up: st['DOUBLE7'] = 1
        if st['IBS']: st['IBS'] = 0 if c[i] > h[i-1] else 1
        elif ibs < 0.2 and up: st['IBS'] = 1
        if i < n-1 and mo[i+1] != mo[i] and up and i > eom_until: eom_until = i+3
        P['RSI2'][i] = st['RSI2']; P['DOUBLE7'][i] = st['DOUBLE7']; P['IBS'][i] = st['IBS']
        P['FIN MOIS'][i] = 1 if i <= eom_until else 0; P['TENDANCE12'][i] = 1 if (c[i] > c[i-252] and up) else 0
    return P

def rets(d, pos, cost):
    c = [x['close'] for x in d]; r = [0.0]*len(d)
    for i in range(1, len(d)): r[i] = pos[i-1]*(c[i]/c[i-1]-1) - cost*abs(pos[i-1]-(pos[i-2] if i >= 2 else 0))
    return r

def curve(r):
    e = 1.0; pk = 1.0; dd = 0.0
    for x in r: e *= 1+x; pk = max(pk, e); dd = max(dd, 1-e/pk)
    return e, dd

def trades(d, pos):
    c = [x['close'] for x in d]; out = []; i = 1
    while i < len(d):
        if pos[i-1] == 1 and (i < 2 or pos[i-2] == 0):
            j = i
            while j < len(d) and pos[j-1] == 1: j += 1
            out.append(c[j-1]/c[i-1]-1); i = j
        else: i += 1
    return out

def report(name, d, cost=0.0001):
    n = len(d); yrs = max(0.5, (d[-1]['time']-d[0]['time'])/31557600); P = engines(d); R = {}
    print("\n=== %s | %d bougies D1 | du %s au %s (%.1f ans) | cout %.2f%% par cote ===" % (name, n, dt.datetime.fromtimestamp(d[0]['time'], dt.timezone.utc).strftime('%d/%m/%Y'), dt.datetime.fromtimestamp(d[-1]['time'], dt.timezone.utc).strftime('%d/%m/%Y'), yrs, cost*100))
    for k, pos in P.items():
        r = rets(d, pos, cost); R[k] = r; t = trades(d, pos); e, dd = curve(r); w = sum(x for x in t if x > 0); l = -sum(x for x in t if x < 0)
        print("%-11s %3d trades | gagnants %2d%% | PF %.2f | rendement %+6.1f%% | baisse max %4.1f%% | en position %2d%%" % (k, len(t), 100*sum(1 for x in t if x > 0)/max(1, len(t)), w/l if l else 9.99, (e-1)*100, dd*100, 100*sum(pos)/n))
    pr = [sum(R[k][i] for k in R)/5 for i in range(n)]; ex = sum(sum(P[k]) for k in P)/(5*n)
    bh = [0.0] + [d[i]['close']/d[i-1]['close']-1 for i in range(1, n)]
    for nm, r in (("PORTEFEUILLE (moyenne des 5)", pr), ("ACHAT-CONSERVATION (100%)", bh), ("ACHAT-CONSERVATION x %d%% (meme exposition)" % round(ex*100), [x*ex for x in bh])):
        e, dd = curve(r); print("%-46s rend. annuel %+5.1f%% | baisse max %4.1f%% | rendement/baisse %.2f" % (nm, ((e**(1/yrs))-1)*100, dd*100, ((e**(1/yrs))-1)/dd if dd else 0))
    ys = {}
    for i in range(n):
        y = dt.datetime.fromtimestamp(d[i]['time'], dt.timezone.utc).year; a = ys.setdefault(y, [1.0, 1.0]); a[0] *= 1+pr[i]; a[1] *= 1+bh[i]
    print("par annee (portefeuille / achat-conservation) : " + " | ".join("%d %+.0f%%/%+.0f%%" % (y, (a[0]-1)*100, (a[1]-1)*100) for y, a in sorted(ys.items())))

if __name__ == '__main__':
    import MetaTrader5 as mt5
    from backtest3 import SYMS
    mt5.initialize()
    for a in ('NAS100', 'SPX500', 'US30', 'GER40'):
        s = SYMS[a]; mt5.symbol_select(s, True)
        r = next((x for x in (mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_D1, 0, k) for k in (6000, 4000, 3000, 2000, 1000)) if x is not None and len(x) > 300), None)
        if r is None: print(a, ": pas de donnees D1"); continue
        report(a, [{'time': int(x['time']), 'open': float(x['open']), 'high': float(x['high']), 'low': float(x['low']), 'close': float(x['close'])} for x in r])
