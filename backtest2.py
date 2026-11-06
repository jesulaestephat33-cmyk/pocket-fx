# Pocket FX - backtest 2 : cassure vs retour a la moyenne, choix sur 60% des donnees, verification sur les 40% restants
import sys, math
from backtest_micro import load, fake, summary

def indic(c):
    n = len(c); cl = [x['close'] for x in c]
    atr = [0]*n; mean = [0]*n; sd = [0]*n; hh = [0]*n; ll = [0]*n; rsi = [50]*n
    g = l = 0
    for i in range(1, n):
        d = cl[i]-cl[i-1]
        if i <= 14: g += max(d, 0)/14; l += max(-d, 0)/14
        else: g = (g*13+max(d, 0))/14; l = (l*13+max(-d, 0))/14
        rsi[i] = 100 if l == 0 else 100-100/(1+g/l)
        if i >= 20:
            w = cl[i-19:i+1]; m = sum(w)/20; mean[i] = m
            sd[i] = math.sqrt(sum((x-m)**2 for x in w)/20)
            hh[i] = max(x['high'] for x in c[i-20:i]); ll[i] = min(x['low'] for x in c[i-20:i])
        if i >= 14: atr[i] = sum(c[j]['high']-c[j]['low'] for j in range(i-13, i+1))/14
    return atr, mean, sd, hh, ll, rsi

TF_MIN = 5
def trades(c, I, kind, k, rr, hold, spread):
    atr, mean, sd, hh, ll, rsi = I; out = []; i = 30; n = len(c)
    while i < n-1:
        a = atr[i]; px = c[i]['close']; side = None
        if a > 0 and c[i]['time']-c[i-30]['time'] < 4200*TF_MIN:
            if kind == 'BRK': side = 'BUY' if px > hh[i] else 'SELL' if px < ll[i] else None
            else: side = 'SELL' if (px > mean[i]+2*sd[i] and rsi[i] > 70) else 'BUY' if (px < mean[i]-2*sd[i] and rsi[i] < 30) else None
        if not side: i += 1; continue
        s = 1 if side == 'BUY' else -1; risk = k*a; sl = px-s*risk; tp = px+s*rr*risk
        res, end, j = 'exp', min(n-1, i+hold), i
        for j in range(i+1, end+1):
            hs = c[j]['low'] <= sl if s > 0 else c[j]['high'] >= sl
            ht = c[j]['high'] >= tp if s > 0 else c[j]['low'] <= tp
            if hs: res = 'loss'; break
            if ht: res = 'win'; break
        cost = spread/risk
        out.append((i, res, rr-cost if res == 'win' else (-1-cost if res == 'loss' else -cost)))
        i = j+1 if res != 'exp' else end+1
    return out

if __name__ == '__main__':
    nums = [x for x in sys.argv[1:] if x.isdigit()]; N = int(nums[0]) if nums else 20000; TF = int(nums[1]) if len(nums) > 1 else 5
    data = {'TEST':(fake(8000), 0.02)} if '--test' in sys.argv else load(N, TF)
    TF_MIN = TF
    P = {a:(c, indic(c), sp) for a, (c, sp) in data.items()}
    hs = (6, 12) if TF == 5 else (4, 8) if TF == 15 else (15, 30)
    res = []
    for kind in ('BRK', 'FADE'):
        for k in (1.0, 1.5):
            for rr in (1.0, 1.5):
                for h in hs:
                    tr, te = [], []
                    for a, (c, I, sp) in P.items():
                        cut = int(len(c)*0.6)
                        for i, r, R in trades(c, I, kind, k, rr, h, sp): (tr if i < cut else te).append((r, R))
                    res.append((summary(tr), summary(te), (kind, k, rr, h)))
    res.sort(key=lambda x: -x[0][3])
    print(f'\nTF M{TF} - choisi sur 60% ancien (APPRENTISSAGE), verifie sur 40% recent (TEST)')
    for (n1, w1, l1, R1), (n2, w2, l2, R2), p in res:
        print(f"{p[0]:4s} SL {p[1]}ATR TP x{p[2]} dure {p[3]:2d} | appr {n1:5d} tr {R1:+7.1f}R | TEST {n2:5d} tr {R2:+7.1f}R reussite {w2/max(1,w2+l2)*100:4.1f}%")
