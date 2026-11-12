s = open('backtest_micro.py').read()
pairs = [
("c[i]['time'] - c[i-60]['time'] > 4200", "c[i]['time'] - c[i-60]['time'] > 4200*P.get('tf', 1)"),
("def load(n):", "def load(n, tf=1):"),
("mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M1, 0, n)", "mt5.copy_rates_from_pos(s, {1: mt5.TIMEFRAME_M1, 5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15}[tf], 0, n)"),
("nums = [x for x in sys.argv[1:] if x.isdigit()]; n = int(nums[0]) if nums else 20000",
 "nums = [x for x in sys.argv[1:] if x.isdigit()]; n = int(nums[0]) if nums else 20000; TF = int(nums[1]) if len(nums) > 1 else 1"),
("else load(n)", "else load(n, TF)"),
("for h in (15, 30)]", "for h in {1: (15, 30), 5: (6, 12), 15: (4, 8)}[TF]]\n    for P in grid: P['tf'] = TF"),
("    best = res[0][1]", "    print('TOTAL meilleur reglage :', f'{res[0][0][3]:+.1f}R sur {res[0][0][0]} trades (TF M{TF})')\n    best = res[0][1]"),
]
for a, b in pairs:
    assert a in s, a
    s = s.replace(a, b, 1)
open('backtest_micro.py', 'w').write(s)
print('patch OK')
