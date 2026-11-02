/* Pocket FX - quand le TP ou le SL d'un signal support/résistance est touché, le gros panneau passe en "Signal terminé"
   (WIN / LOSS) au lieu de rester sur BUY NOW / SELL NOW. */
(function(root){
'use strict';
if(typeof PFXJ === 'undefined' || !PFXJ.finished) return;
const _setState = root.setState, _updateMarker = root.updateMarker;
if(typeof _setState !== 'function') return;

root.setState = function(kind, label, confidence, level){
  if(kind === 'buy' || kind === 'sell'){
    const t = PFXJ.finished(currentAsset.id, kind.toUpperCase(), level);
    if(t){
      _setState('wait', 'Signal terminé', null, null);
      const conf = document.getElementById('confidenceText');
      const win = t.result === 'win';
      if(conf) conf.innerHTML = `<b style="color:${win ? '#29D398' : '#FF5C72'}">${win ? 'WIN +' + t.r.toFixed(2) + 'R' : 'LOSS -1R'}</b> · ${t.side} ${t.asset} · en attente d'un nouveau signal`;
      return;
    }
  }
  return _setState.apply(this, arguments);
};
if(typeof _updateMarker === 'function'){
  root.updateMarker = function(data){
    if(data && (data.state === 'buy' || data.state === 'sell') && PFXJ.finished(currentAsset.id, data.state.toUpperCase(), data.level))
      return _updateMarker.call(this, Object.assign({}, data, { state:'wait' }));
    return _updateMarker.apply(this, arguments);
  };
}
})(window);
