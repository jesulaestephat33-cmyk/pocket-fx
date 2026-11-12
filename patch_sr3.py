s = open('bt_sr.py').read()
if "P.get('inv')" in s: print('bt_sr.py : deja OK')
else:
    a = "side, entry, sl, tp, risk = sg\n"
    assert a in s, 'ligne 1 introuvable'
    s = s.replace(a, a + "        if P.get('inv'): side = 'down' if side == 'up' else 'up'; sl, tp = tp, sl; risk = abs(entry-sl)\n", 1)
    b = "            td = A.trend(j)\n            if td != d: res = ('rev', b['close'], j); break"
    assert b in s, 'ligne 2 introuvable'
    s = s.replace(b, "            td = A.trend(j)\n            if td != d and not P.get('inv'): res = ('rev', b['close'], j); break", 1)
    open('bt_sr.py', 'w').write(s); print('bt_sr.py : patch OK')
r = open('bt_sr_run.py').read()
if 'INVERSE' in r: print('bt_sr_run.py : deja OK')
else:
    c = "VARIANTES = [('ACTUEL (ton backend)', {}),"
    assert c in r, 'ligne 3 introuvable'
    r = r.replace(c, "VARIANTES = [('ACTUEL (ton backend)', {}), ('INVERSE (SL<->TP, sens inverse)', dict(inv=1)), ('INVERSE sans spread (brut)', dict(inv=1, cost=0)),", 1)
    d = "t-stat {s['t']:+.2f}\")"
    assert d in r, 'ligne 4 introuvable'
    r = r.replace(d, "t-stat {s['t']:+.2f}\")\n        print(f\"{'':26s} PAR SEMAINE : {s['n']/wk:.0f} signaux, {s['tp']/wk:.0f} TP, {s['sl']/wk:.0f} SL, {s['exp']/wk:.0f} expires, {s['rev']/wk:.0f} sorties tendance (periode {wk:.1f} semaines)\")", 1)
    e = "        tr2 = [(k, kd, R) for _, k, kd, R in tr]"
    assert e in r, 'ligne 5 introuvable'
    r = r.replace(e, "        wk = max(0.1, (list(data.values())[0][0][-1]['time'] - list(data.values())[0][0][0]['time'])/604800)\n" + e, 1)
    open('bt_sr_run.py', 'w').write(r); print('bt_sr_run.py : patch OK')
