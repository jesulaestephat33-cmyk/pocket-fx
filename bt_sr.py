# Pocket FX - backtest du moteur Support/Resistance du backend (zones H1, rejet M1, SL derriere la zone, TP scalp)
import sys, math, bisect

BASE = dict(entry_touches=2, target_touches=3, sl_max=3.0, tp_atr=4.0, min_rr=1.2, hold=60, zone_every=10)
KE = 2/51
W = [(1-KE)**49] + [KE*(1-KE)**(49-i) for i in range(1, 50)]

def atr14(rates):
    trs = [max(rates[i]['high']-rates[i]['low'], abs(rates[i]['high']-rates[i-1]['close']), abs(rates[i]['low']-rates[i-1]['close'])) for i in range(1, len(rates))]
    return sum(trs[-14:])/min(14, len(trs)) if trs else 0

def clusters(rates, price, window=3):
    piv = []
    for i in range(window, len(rates)-window):
        hs = [rates[j]['high'] for j in range(i-window, i+window+1)]; ls = [rates[j]['low'] for j in range(i-window, i+window+1)]
        if rates[i]['high'] == max(hs): piv.append(('resistance', rates[i]['high']))
        if rates[i]['low'] == min(ls): piv.append(('support', rates[i]['low']))
    tol = max(atr14(rates)*0.5, price*0.0005); out = {}
    for kind in ('support', 'resistance'):
        cl = []
        for lvl in sorted(l for k, l in piv if k == kind):
            for c in cl:
                if abs(lvl-c['avg']) <= tol: c['levels'].append(lvl); c['avg'] = sum(c['levels'])/len(c['levels']); break
            else: cl.append({'levels':[lvl], 'avg':lvl})
        out[kind] = cl
    return out, tol

class Asset:
    def __init__(self, m1, h1, spread):
        self.m1, self.h1, self.spread = m1, h1, spread
        self.h1t = [b['time'] for b in h1]; self.h1c = [b['close'] for b in h1]
        self.base = {}; self.fo = None; self.fh = None; self.hs = None   # etat de la bougie H1 en formation
        self.zc = None; self.zk = -10**9

    def advance(self, k):                      # met a jour la bougie H1 en formation avec le M1 numero k
        b = self.m1[k]; hs = b['time'] - b['time'] % 3600
        if hs != self.hs: self.hs = hs; self.fo = b['open']; self.fh = b['high']; self.fl = b['low']
        else: self.fh = max(self.fh, b['high']); self.fl = min(self.fl, b['low'])
        self.idx = bisect.bisect_left(self.h1t, hs)          # nb de bougies H1 terminees
        self.forming = {'time':hs, 'open':self.fo, 'high':self.fh, 'low':self.fl, 'close':b['close']}

    def trend(self, k):
        i = self.idx
        if i < 49: return None
        if i not in self.base: self.base[i] = sum(W[j]*self.h1c[i-49+j] for j in range(49))
        e = self.base[i] + W[49]*self.m1[k]['close']; last = self.m1[k]['close']
        return 'up' if last > e*1.0005 else 'down' if last < e*0.9995 else 'flat'

    def zones(self, k, price, every):
        if self.zc is None or k - self.zk >= every or self.zhs != self.hs:
            rates = self.h1[max(0, self.idx-149):self.idx] + [self.forming]
            self.zc = clusters(rates, price); self.zk = k; self.zhs = self.hs
        return self.zc

    def signal(self, k, direction, P):
        m1 = self.m1; price = m1[k]['close']
        cl, tol = self.zones(k, price, P['zone_every'])
        want = 'support' if direction == 'up' else 'resistance'
        if not cl[want]: return None
        z = min(cl[want], key=lambda c: abs(c['avg']-price)); level = z['avg']; touches = len(z['levels'])
        rej = False
        for b in (m1[j] for j in range(k, max(-1, k-5), -1)):
            if direction == 'up': ok = level-tol*3 <= b['low'] <= level+tol
            else: ok = level-tol <= b['high'] <= level+tol*3
            if not ok: continue
            rg = b['high']-b['low']
            if rg <= 0: continue
            lw = min(b['open'], b['close'])-b['low']; uw = b['high']-max(b['open'], b['close'])
            if direction == 'up' and b['close'] > b['open'] and lw/rg > 0.4: rej = True; break
            if direction == 'down' and b['close'] < b['open'] and uw/rg > 0.4: rej = True; break
        if not rej: return None
        buf = tol*1.2; body = m1[k-14:k]
        bar = sum(b['high']-b['low'] for b in body)/len(body)
        sl = round(level-buf, 2) if direction == 'up' else round(level+buf, 2)
        risk = price-sl if direction == 'up' else sl-price
        if touches < P['entry_touches'] or risk <= 0 or risk > bar*P['sl_max']: return None
        reward = bar*P['tp_atr']
        opp = cl['resistance' if direction == 'up' else 'support']
        cand = [c for c in opp if (c['avg'] > price if direction == 'up' else c['avg'] < price)]
        if cand:
            t = min(cand, key=lambda c: abs(c['avg']-price))
            if len(t['levels']) >= P['target_touches']:
                dist = (t['avg']-price) if direction == 'up' else (price-t['avg'])
                if 0 < dist < reward: reward = dist
        if reward < risk*P['min_rr']: return None
        tp = round(price+reward, 2) if direction == 'up' else round(price-reward, 2)
        if risk < max(tol*0.5, price*0.0002): return None
        return direction, price, sl, tp, risk

def simulate(m1, h1, spread, P):
    A = Asset(m1, h1, spread); trades = []; k = 60; n = len(m1); cool = -1
    while k < n-1:
        A.advance(k)
        if k < cool: k += 1; continue
        d = A.trend(k)
        if d in (None, 'flat'): k += 1; continue
        sg = A.signal(k, d, P)
        if not sg: k += 1; continue
        side, entry, sl, tp, risk = sg
        if spread/risk > P.get('spread_max', 9) or not (P.get('h0', 0) <= (m1[k]['time']//3600) % 24 < P.get('h1', 24)): k += 1; continue
        s = 1 if side == 'up' else -1; k0 = k; res = None
        for j in range(k+1, min(n, k+1+P['hold'])):
            b = m1[j]; A.advance(j)
            if s*((b['low'] if s > 0 else b['high'])-sl) <= 0: res = ('sl', sl, j); break
            if s*((b['high'] if s > 0 else b['low'])-tp) >= 0: res = ('tp', tp, j); break
            td = A.trend(j)
            if td != d: res = ('rev', b['close'], j); break
        if res is None: j = min(n-1, k+P['hold']); res = ('exp', m1[j]['close'], j)
        kind, ex, j = res; R = (ex-entry)*s/risk - P.get('cost', 1)*spread/risk
        trades.append((k0, kind, R)); k = j+1
        if kind in ('tp', 'sl'): cool = j+1+5
    return trades

def summ(tr):
    n = len(tr); R = [x[2] for x in tr]; tot = sum(R); mu = tot/n if n else 0
    sd = math.sqrt(sum((x-mu)**2 for x in R)/(n-1)) if n > 1 else 0
    t = mu/(sd/math.sqrt(n)) if sd > 0 else 0
    c = lambda kd: sum(1 for x in tr if x[1] == kd)
    return dict(n=n, tp=c('tp'), sl=c('sl'), rev=c('rev'), exp=c('exp'), R=tot, mu=mu, t=t)
