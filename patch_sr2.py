s = open('bt_sr.py').read()
if "spread_max" not in s:
    a = "side, entry, sl, tp, risk = sg; s = 1 if side == 'up' else -1; k0 = k; res = None"
    assert a in s, 'ligne simulate introuvable'
    s = s.replace(a, "side, entry, sl, tp, risk = sg\n        if spread/risk > P.get('spread_max', 9) or not (P.get('h0', 0) <= (m1[k]['time']//3600) % 24 < P.get('h1', 24)): k += 1; continue\n        s = 1 if side == 'up' else -1; k0 = k; res = None", 1)
    b = "R = (ex-entry)*s/risk - spread/risk"
    assert b in s, 'ligne R introuvable'
    s = s.replace(b, "R = (ex-entry)*s/risk - P.get('cost', 1)*spread/risk", 1)
    open('bt_sr.py', 'w').write(s); print('bt_sr.py : patch OK')
else: print('bt_sr.py : deja OK')
r = open('bt_sr_run.py').read()
if "spread <= 20%" not in r:
    i = r.index("VARIANTES = ["); j = r.index("def fake")
    new = ("VARIANTES = [('ACTUEL (ton backend)', {}), ('ACTUEL sans spread (brut)', dict(cost=0)), ('spread <= 20% du risque', dict(spread_max=0.2)),\n"
           "             ('spread <= 10% du risque', dict(spread_max=0.1)), ('heures 7h-17h UTC', dict(h0=7, h1=17)),\n"
           "             ('heures 7-17 + spread <= 20%', dict(h0=7, h1=17, spread_max=0.2)), ('TP 8 + spread <= 20%', dict(tp_atr=8.0, spread_max=0.2))]\n\n")
    open('bt_sr_run.py', 'w').write(r[:i] + new + r[j:]); print('bt_sr_run.py : patch OK')
else: print('bt_sr_run.py : deja OK')
