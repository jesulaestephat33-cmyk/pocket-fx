# Pocket FX - backtest 4 : 5 candidats fixes, coupes en 5 tranches de temps + detail par actif (M15, stop suiveur, spread inclus)
import sys, math
from backtest3 import load, fake, indic, trades

CANDS = [('DON55', 3.0, 'Europe 7-12h', (7, 12)), ('DON20', 3.0, 'Europe 7-12h', (7, 12)),
         ('PB', 2.0, 'toute la journee', (0, 24)), ('PB', 3.0, 'toute la journee', (0, 24)), ('PB', 3.0, 'Europe 7-12h', (7, 12))]

if __name__ == '__main__':
    nums = [x for x in sys.argv[1:] if x.isdigit()]; N = int(nums[0]) if nums else 30000; TF = int(nums[1]) if len(nums) > 1 else 15
    data = {'TEST':(fake(8000), 0.05)} if '--test' in sys.argv else load(N, TF)
    P = {a:(c, indic(c), sp) for a, (c, sp) in data.items()}
    print(f'\nTF {TF} min, {N} bougies demandees. R net par tranche de temps (1 = plus ancien ... 5 = plus recent)')
    for kind, m, hn, hrs in CANDS:
        sl = [0.0]*5; allR = []; per = {}
        for a, (c, I, sp) in P.items():
            n = len(c); rs = []
            for i, R in trades(c, I, kind, m, hrs, sp):
                sl[min(4, i*5//n)] += R; allR.append(R); rs.append(R)
            per[a] = (len(rs), sum(rs))
        nn = len(allR); mu = sum(allR)/max(1, nn); sd = math.sqrt(sum((x-mu)**2 for x in allR)/max(1, nn-1)) if nn > 1 else 1
        t = mu/(sd/math.sqrt(nn)) if nn > 1 and sd > 0 else 0
        print(f"\n{kind} stop {m}ATR {hn}: {nn} trades, total {sum(allR):+.1f}R, moy {mu:+.3f}R, t-stat {t:+.2f} (il faut > 2 pour y croire)")
        print('  tranches :', ' '.join(f'{x:+7.1f}R' for x in sl), '  -> positives :', sum(1 for x in sl if x > 0), '/5')
        print('  par actif:', '  '.join(f'{a} {v[1]:+.1f}R({v[0]})' for a, v in per.items()))
