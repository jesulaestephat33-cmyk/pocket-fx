# Pocket FX - exporte l'historique MT5 (bougies + spread) vers fibdata.js pour tester le Signal Fib dans le navigateur
import sys, json
from backtest3 import load
nums = [x for x in sys.argv[1:] if x.isdigit()]
tf = int(nums[0]) if nums else 5; n = int(nums[1]) if len(nums) > 1 else 20000
data = load(n, tf); out = {'tf': tf, 'assets': {}}
for a, (c, sp) in data.items():
    out['assets'][a] = {'spread': sp, 'c': [[x['time'], x['open'], x['high'], x['low'], x['close']] for x in c]}
open('fibdata.js', 'w').write('window.FIBDATA = ' + json.dumps(out, separators=(',', ':')) + ';')
print('fibdata.js ecrit :', {a: len(v['c']) for a, v in out['assets'].items()}, '| TF M%d' % tf)
