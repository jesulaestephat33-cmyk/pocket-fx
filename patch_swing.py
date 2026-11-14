import re
b = open('pocket_fx_backend.py', encoding='utf-8').read()
if '"D1"' not in b:
    m = re.search(r'TF_MAP\s*=\s*\{', b)
    assert m, 'TF_MAP introuvable dans le backend'
    b = b[:m.end()] + '"D1": mt5.TIMEFRAME_D1, ' + b[m.end():]
    open('pocket_fx_backend.py', 'w', encoding='utf-8').write(b); print('backend : D1 ajoute')
else: print('backend : deja OK')
h = open('pocket-fx.html', encoding='utf-8').read()
if 'pfx-swing.js' not in h:
    m = re.search(r'[ \t]*<script src="pfx-finished\.js"></script>', h)
    tag = '<script src="pfx-swing.js"></script>\n'
    h = h[:m.start()] + tag + h[m.start():] if m else h.replace('</body>', tag + '</body>', 1)
    open('pocket-fx.html', 'w', encoding='utf-8').write(h); print('html : balise ajoutee')
else: print('html : deja OK')
