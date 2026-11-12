import re
b = open('pocket_fx_backend.py', encoding='utf-8').read()
if '"M15"' not in b:
    a = '"M5": mt5.TIMEFRAME_M5, "H1"'
    assert a in b, 'TF_MAP introuvable dans le backend'
    b = b.replace(a, '"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "H1"', 1)
    open('pocket_fx_backend.py', 'w', encoding='utf-8').write(b); print('backend : M15 ajoute')
else: print('backend : deja OK')
h = open('pocket-fx.html', encoding='utf-8').read()
if 'pfx-trend.js' not in h:
    m = re.search(r'[ \t]*<script src="pfx-finished\.js"></script>', h)
    tag = '<script src="pfx-trend.js"></script>\n'
    h = h[:m.start()] + tag + h[m.start():] if m else h.replace('</body>', tag + '</body>', 1)
    open('pocket-fx.html', 'w', encoding='utf-8').write(h); print('html : balise ajoutee')
else: print('html : deja OK')
