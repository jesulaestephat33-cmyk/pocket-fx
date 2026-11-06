# Pocket FX - banc d'essai de 8 strategies classiques + 1 temoin au hasard (spread inclus, apprentissage 60% / test 40%)
import sys, math, random

def ind(c):
    n = len(c); cl = [x['close'] for x in c]; A = [0.0]*n; e9 = [0.0]*n; e21 = [0.0]*n; s20 = [0.0]*n; sd = [0.0]*n; s200 = [0.0]*n; r2 = [50.0]*n
    day = [x['time']//86400 for x in c]; avg = [0.0]*n; pdh = [None]*n; pdl = [None]*n; dpos = [0]*n; g = l = 0.0; hi = {}; lo = {}
    for i in range(n):
        e9[i] = cl[i] if i == 0 else cl[i]*0.2 + e9[i-1]*0.8; e21[i] = cl[i] if i == 0 else cl[i]*2/22 + e21[i-1]*20/22
        if i >= 14: A[i] = sum(c[j]['high']-c[j]['low'] for j in range(i-13, i+1))/14
        if i >= 20: w = cl[i-19:i+1]; m = sum(w)/20; s20[i] = m; sd[i] = math.sqrt(sum((x-m)**2 for x in w)/20)
        if i >= 200: s200[i] = sum(cl[i-199:i+1])/200
        if i >= 1:
            d = cl[i]-cl[i-1]
            if i <= 2: g += max(d, 0)/2; l += max(-d, 0)/2
            else: g = (g+max(d, 0))/2; l = (l+max(-d, 0))/2
            r2[i] = 100 if l == 0 else 100-100/(1+g/l)
        dd = day[i]; hi[dd] = max(hi.get(dd, -1e18), c[i]['high']); lo[dd] = min(lo.get(dd, 1e18), c[i]['low'])
        dpos[i] = 0 if i == 0 or day[i-1] != dd else dpos[i-1]+1
        tp = (c[i]['high']+c[i]['low']+c[i]['close'])/3
        avg[i] = tp if dpos[i] == 0 else (avg[i-1]*dpos[i] + tp)/(dpos[i]+1)
        pdh[i] = hi.get(dd-1); pdl[i] = lo.get(dd-1)
    # supertrend (10, 3)
    st = [0]*n; fu = fl = None; tr = 1
    for i in range(10, n):
        a10 = sum(c[j]['high']-c[j]['low'] for j in range(i-9, i+1))/10; mid = (c[i]['high']+c[i]['low'])/2
        u, lw = mid+3*a10, mid-3*a10
        fu = u if fu is None or u < fu or cl[i-1] > fu else fu; fl = lw if fl is None or lw > fl or cl[i-1] < fl else fl
        tr = 1 if cl[i] > fu else -1 if cl[i] < fl else tr; st[i] = tr
    return dict(A=A, e9=e9, e21=e21, s20=s20, sd=sd, s200=s200, r2=r2, avg=avg, pdh=pdh, pdl=pdl, dpos=dpos, day=day, st=st)

def strat(name, c, I, tfm):
    n = len(c); A = I['A']; out = []
    if name.startswith('ORB') or name.startswith('FADEORB'):
        _, hh, mm = name.split('_'); st0 = int(hh)*3600 + int(mm)*60; nr = max(1, 60//tfm); done = set(); i = 0
        while i < n-nr-1:
            t = c[i]['time'] % 86400; d = I['day'][i]
            if t == st0 and d not in done and c[i+nr-1]['time'] == c[i]['time'] + (nr-1)*tfm*60:
                rh = max(x['high'] for x in c[i:i+nr]); rl = min(x['low'] for x in c[i:i+nr])
                for j in range(i+nr, min(n, i+nr+240//tfm)):
                    if c[j]['close'] > rh or c[j]['close'] < rl:
                        s = 1 if c[j]['close'] > rh else -1; risk = c[j]['close']-rl if s > 0 else rh-c[j]['close']
                        if 0 < risk <= 3*A[j]: out.append((j, -s, 1.5*risk, risk, 24) if name.startswith('FADE') else (j, s, risk, 1.5*risk, 24))
                        break
                done.add(d)
            i += 1
    for i in range(210, n-1):
        a = A[i]
        if a <= 0: continue
        px = c[i]['close']
        if name == 'RSI2' and I['r2'][i] < 10 and px > I['s200'][i]: out.append((i, 1, 2*a, 1.5*a, 12))
        elif name == 'RSI2' and I['r2'][i] > 90 and px < I['s200'][i]: out.append((i, -1, 2*a, 1.5*a, 12))
        if name == 'SUPERTREND' and I['st'][i] != I['st'][i-1] and I['st'][i-1] != 0: out.append((i, I['st'][i], 2*a, 4*a, 48))
        if name == 'EMA9_21':
            if I['e9'][i] > I['e21'][i] and I['e9'][i-1] <= I['e21'][i-1]: out.append((i, 1, 2*a, 4*a, 48))
            if I['e9'][i] < I['e21'][i] and I['e9'][i-1] >= I['e21'][i-1]: out.append((i, -1, 2*a, 4*a, 48))
        if name == 'BB_SQUEEZE' and I['s20'][i] > 0 and i > 120:
            bw = [4*I['sd'][j]/I['s20'][j] for j in range(i-99, i+1)]; up = I['s20'][i]+2*I['sd'][i]; dn = I['s20'][i]-2*I['sd'][i]
            if bw[-1] <= sorted(bw)[19]:
                if px > up and c[i-1]['close'] <= up: out.append((i, 1, 1.5*a, 3*a, 24))
                if px < dn and c[i-1]['close'] >= dn: out.append((i, -1, 1.5*a, 3*a, 24))
        if name == 'MOY_JOUR' and I['dpos'][i] >= 8:
            dev = (px-I['avg'][i])/a
            if dev < -2.5: out.append((i, 1, 1.5*a, 1.5*a, 16))
            if dev > 2.5: out.append((i, -1, 1.5*a, 1.5*a, 16))
        if name == 'BALAYAGE_VEILLE' and I['pdh'][i] is not None:
            if c[i]['high'] > I['pdh'][i] and px < I['pdh'][i]:
                risk = c[i]['high']+0.2*a-px
                if 0 < risk <= 3*a: out.append((i, -1, risk, 2*risk, 24))
            if c[i]['low'] < I['pdl'][i] and px > I['pdl'][i]:
                risk = px-(c[i]['low']-0.2*a)
                if 0 < risk <= 3*a: out.append((i, 1, risk, 2*risk, 24))
    if name == 'HASARD':
        rnd = random.Random(5)
        for i in range(210, n-1, 40):
            if A[i] > 0: out.append((i, rnd.choice((1, -1)), 1.5*A[i], 1.5*A[i], 24))
    return out

def trades(c, sigs, spread):
    res = []; free = 0
    for i, s, risk, tpd, hold in sorted(sigs):
        if i < free: continue
        e = c[i]['close']; sl = e-s*risk; tp = e+s*tpd; ex = None; j = i
        for j in range(i+1, min(len(c), i+1+hold)):
            if s*((c[j]['low'] if s > 0 else c[j]['high'])-sl) <= 0: ex = sl; break
            if s*((c[j]['high'] if s > 0 else c[j]['low'])-tp) >= 0: ex = tp; break
        if ex is None: j = min(len(c)-1, i+hold); ex = c[j]['close']
        res.append((i, (ex-e)*s/risk, spread/risk)); free = j+1
    return res

NAMES = ['ORB_7_0', 'ORB_8_0', 'ORB_13_30', 'ORB_14_30', 'RSI2', 'SUPERTREND', 'EMA9_21', 'BB_SQUEEZE', 'MOY_JOUR', 'BALAYAGE_VEILLE', 'HASARD']

def fake(n=9000):
    random.seed(8); p = 100.0; c = []; t = 1700000000 - 1700000000 % 86400
    for i in range(n):
        o = p; p += random.gauss(0, 0.2); c.append({'time':t+900*i, 'open':o, 'high':max(o, p)+abs(random.gauss(0, .08)), 'low':min(o, p)-abs(random.gauss(0, .08)), 'close':p})
    return {'TEST': (c, 0.03)}

if __name__ == '__main__':
    nums = [x for x in sys.argv[1:] if x.isdigit()]; tfm = int(nums[0]) if nums else 15; N = int(nums[1]) if len(nums) > 1 else 20000
    if '--test' in sys.argv: data = fake()
    else:
        from backtest3 import load
        data = load(N, tfm)
    if 'fadescan' in sys.argv: NAMES[:] = ['FADEORB_%d_%d' % (h, m) for h in range(24) for m in (0, 30)]
    if 'orbscan' in sys.argv: NAMES[:] = ['ORB_%d_%d' % (h, m) for h in range(24) for m in (0, 30)]
    pre = {a:(c, ind(c), sp) for a, (c, sp) in data.items()}
    print(f"\nTF M{tfm} | R net, spread inclus | appr = 60% ancien, TEST = 40% recent | actifs positifs (net)")
    for nm in NAMES:
        allr = []; tr = []; te = []; pos = 0
        for a, (c, I, sp) in pre.items():
            cut = int(len(c)*0.6); t = trades(c, strat(nm, c, I, tfm), sp); net = sum(r-co for _, r, co in t)
            pos += 1 if net > 0 else 0
            for i, r, co in t: allr.append((r, co)); (tr if i < cut else te).append(r-co)
        n = len(allr); nets = [r-co for r, co in allr]; mu = sum(nets)/n if n else 0
        sd = math.sqrt(sum((x-mu)**2 for x in nets)/(n-1)) if n > 1 else 0; tt = mu/(sd/math.sqrt(n)) if sd > 0 else 0
        print(f"{nm:16s} {n:5d} trades | brut {sum(r for r, _ in allr):+7.1f}R net {sum(nets):+7.1f}R moy {mu:+.3f}R t-stat {tt:+5.2f} | appr {sum(tr):+7.1f}R TEST {sum(te):+7.1f}R | {pos}/{len(pre)}")
