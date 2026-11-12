s = open('bt_sr.py').read()
old = "sl, tp = tp, sl; risk = abs(entry-sl)"
new = "sl, tp = tp, sl; risk = abs(entry-sl); tp = entry + (1 if side == 'up' else -1) * P.get('tpk', 1) * abs(tp-entry)"
if "P.get('tpk'" in s: print("bt_sr.py : deja patche")
elif old in s: open('bt_sr.py','w').write(s.replace(old, new)); print("bt_sr.py : patch OK")
else: print("bt_sr.py : ERREUR")
r = open('bt_sr_run.py').read()
i = r.index("VARIANTES = ["); j = r.index("\n", r.index("'TP 8 + spread <= 20%'"))
nv = ("VARIANTES = [('INVERSE TP x1 (base)', dict(inv=1)), ('INVERSE TP x1.5', dict(inv=1, tpk=1.5)), ('INVERSE TP x2', dict(inv=1, tpk=2)),\n"
      "             ('INVERSE TP x3', dict(inv=1, tpk=3)), ('INVERSE TP x2 hold 120', dict(inv=1, tpk=2, hold=120)), ('INVERSE TP x3 hold 120', dict(inv=1, tpk=3, hold=120)),\n"
      "             ('INVERSE TP x2 brut', dict(inv=1, tpk=2, cost=0))]")
if "tpk" in r: print("bt_sr_run.py : deja patche")
else: open('bt_sr_run.py','w').write(r[:i] + nv + r[j:]); print("bt_sr_run.py : patch OK")
