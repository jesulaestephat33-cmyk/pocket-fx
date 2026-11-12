# Pocket FX - replique du script TradingView "ORB" (NY 09:30-09:45, trade 09:45-16:00, RR 1.5, SL cote oppose, filtre EMA50 H1)
import sys, math, datetime as dt

def ny_off(ts):
    d = dt.datetime.utcfromtimestamp(ts); y = d.year
    m = dt.datetime(y, 3, 1); m += dt.timedelta(days=(6 - m.weekday()) % 7 + 7); n = dt.datetime(y, 11, 1); n += dt.timedelta(days=(6 - n.weekday()) % 7)
    return -4*3600 if m + dt.timedelta(hours=7) <= d < n + dt.timedelta(hours=6) else -5*3600

def run(c, h1, sp, use_f=True, rr=1.5):
    e = []; v = None
    for x in h1: v = x['close'] if v is None else x['close']*2/51 + v*49/51; e.append(v)
    ht = [x['time'] for x in h1]; out = []; done = set(); n = len(c); i = 0
    while i < n - 4:
        t = c[i]['time'] + ny_off(c[i]['time']); day = t // 86400; mod = t % 86400
        if mod == 9*3600 + 1800 and day not in done and c[i+2]['time'] - c[i]['time'] == 600:
            done.add(day); rh = max(c[i]['high'], c[i+1]['high']); rl = min(c[i]['low'], c[i+1]['low']); j = i + 2
            while j < n:
                tj = c[j]['time'] + ny_off(c[j]['time'])
                if tj // 86400 != day or tj % 86400 >= 16*3600: break
                cl = c[j]['close']
                if cl > rh or cl < rl:
                    s = 1 if cl > rh else -1; k = max(0, sum(1 for q in ht if q + 3600 <= c[j]['time']) - 1); ok = True
                    if use_f and k > 0: ok = (h1[k]['close'] > e[k]) if s > 0 else (h1[k]['close'] < e[k])
                    risk = abs(cl - (rl if s > 0 else rh))
                    if ok and risk > 0:
                        sl = cl - s*risk; tp = cl + s*rr*risk; res = None; m = j + 1
                        while m < n:
                            tm = c[m]['time'] + ny_off(c[m]['time'])
                            if tm // 86400 != day or tm % 86400 >= 16*3600: res = (c[m-1]['close'] - cl)*s/risk; break
                            b = c[m]
                            if (b['low'] <= sl if s > 0 else b['high'] >= sl): res = -1.0; break
                            if (b['high'] >= tp if s > 0 else b['low'] <= tp): res = rr; break
                            m += 1
                        if res is not None: out.append((c[j]['time'], s, res - sp/risk))
                    break
                j += 1
        i += 1
    return out

def stat(r):
    n = len(r)
    if n < 2: return "%d trades" % n
    mu = sum(r)/n; sd = math.sqrt(sum((x-mu)**2 for x in r)/(n-1)) or 1e-9
    return "%3d trades | gagnants %2d%% | net %+6.1fR moy %+.3fR t-stat %+.2f" % (n, 100*sum(1 for x in r if x > 0)/n, sum(r), mu, mu/sd*math.sqrt(n))

if __name__ == '__main__':
    from backtest3 import load
    d5 = load(20000, 5); d60 = load(3000, 60); allr = []
    print("\nORB NY 09:30-09:45 | RR 1.5 | SL cote oppose | spread inclus")
    for use_f in (True, False):
        print("\n-- %s --" % ("AVEC filtre tendance H1 (comme ton script)" if use_f else "SANS filtre"))
        allr = []
        for a, (c, sp) in d5.items():
            if a not in d60: continue
            o = run(c, d60[a][0], sp, use_f); allr += [x[2] for x in o]; print("%-8s %s" % (a, stat([x[2] for x in o])))
            if a == 'XAUUSD' and use_f:
                last = [x for x in o if x[0] >= c[-1]['time'] - 7*86400]
                print("   XAUUSD 7 derniers jours :", ", ".join("%s %s %+.2fR" % (dt.datetime.utcfromtimestamp(x[0]).strftime('%d/%m'), 'BUY' if x[1] > 0 else 'SELL', x[2]) for x in last) or "aucun trade")
        print("%-8s %s" % ("TOTAL", stat(allr)))
