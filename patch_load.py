s = open('backtest3.py').read()
old = "r = mt5.copy_rates_from_pos(s, T, 0, n)"
new = "r = next((x for x in (mt5.copy_rates_from_pos(s, T, 0, k) for k in (n, n//2, n//4, n//8, n//16)) if x is not None and len(x) > 0), None); print(a, 'bougies chargees :', 0 if r is None else len(r))"
if new in s: print('deja OK')
else:
    assert old in s, 'ligne introuvable'
    open('backtest3.py', 'w').write(s.replace(old, new, 1)); print('patch OK')
