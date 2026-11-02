/* Pocket FX - cycle de vie du signal dans le gros panneau :
   BUY NOW / SELL NOW (clignotant) pendant les 3 premières minutes, puis BUY EN COURS / SELL EN COURS (fixe, avec le résultat
   actuel), puis "Signal terminé" (WIN / LOSS) ou "Signal expiré". Un SL collé à l'entrée est signalé comme invalide. */
(function(root){
'use strict';
if(typeof PFXJ === 'undefined' || !PFXJ.finished) return;
const NOW_MIN = 3;                                  // durée du clignotement "NOW" (minutes)
const _setState = root.setState, _updateMarker = root.updateMarker;
if(typeof _setState !== 'function') return;

// on garde la dernière réponse /api/signal et le dernier prix de chaque actif
const lastSig = {}, lastPx = {};
const _fetch = root.fetch.bind(root);
root.fetch = function(url, o){
  const p = _fetch(url, o);
  try{
    const u = String(url), a = new URL(u, location.href).searchParams.get('asset');
    const isSig = u.indexOf('/api/signal') >= 0, isCan = u.indexOf('/api/candles') >= 0;
    if(a && (isSig || isCan)){
      // la réponse n'est rendue à la page qu'après stockage : setState verra toujours la donnée à jour
      return p.then(r => r.clone().json().then(d => {
        if(isSig) lastSig[a] = d;
        else if(Array.isArray(d) && d.length) lastPx[a] = d[d.length-1].close;
        return r;
      }).catch(() => r));
    }
  }catch(e){}
  return p;
};
const fp = p => Math.abs(p) >= 100 ? (+p).toFixed(2) : (+p).toFixed(4);

root.setState = function(kind, label, confidence, level){
  if(kind === 'buy' || kind === 'sell'){
    const asset = currentAsset.id, side = kind.toUpperCase();
    const t = PFXJ.finished(asset, side, level);
    if(t){
      const win = t.result === 'win', exp = t.result === 'expired';
      _setState('wait', exp ? 'Signal expiré' : 'Signal terminé', null, null);
      const conf = document.getElementById('confidenceText');
      if(conf) conf.innerHTML = exp ? `<b style="color:#F5B841">EXPIRÉ</b> · ${t.side} ${t.asset} · ni TP ni SL touché en ${PFXJ.maxMin} min · en attente d'un nouveau signal`
        : `<b style="color:${win ? '#29D398' : '#FF5C72'}">${win ? 'WIN +' + t.r.toFixed(2) + 'R' : 'LOSS -1R'}</b> · ${t.side} ${t.asset} · en attente d'un nouveau signal`;
      return;
    }
    const d = lastSig[asset];
    if(d && d.state === kind && d.signal_time){
      const ageMin = (Date.now()/1000 - d.signal_time) / 60;
      const entry = +(d.entry || d.price_exness), sl = +d.sl, tp = +d.tp;
      const wrong = kind === 'buy' ? !(sl < entry && entry < tp) : !(tp < entry && entry < sl);
      const bad = wrong || (entry > 0 && sl > 0 && Math.abs(entry - sl) < entry * 0.0002);
      if(bad || ageMin >= NOW_MIN){
        const r = _setState.apply(this, arguments);
        const panel = document.getElementById('signalPanel'), st = document.getElementById('signalState'), conf = document.getElementById('confidenceText');
        if(panel){ panel.classList.remove('alert'); panel.style.removeProperty('--flash-color'); }
        if(bad){
          if(st){ st.textContent = 'SIGNAL INVALIDE'; st.className = 'signal-state wait'; }
          if(conf) conf.innerHTML = `<b style="color:#F5B841">${wrong ? 'Signal incohérent : SL/TP du mauvais côté du prix' : "SL trop proche de l'entrée (" + fp(Math.abs(entry - sl)) + ")"}</b> · ne pas prendre`;
        } else {
          const px = lastPx[asset];
          let pl = '';
          if(px && entry && sl && entry !== sl){
            const dir = side === 'BUY' ? 1 : -1, rr = (px - entry) * dir / Math.abs(entry - sl);
            pl = ` · en cours : <b style="color:${rr >= 0 ? '#29D398' : '#FF5C72'}">${rr >= 0 ? '+' : ''}${rr.toFixed(2)}R</b>`;
          }
          if(st) st.textContent = side + ' EN COURS';
          if(conf) conf.innerHTML = `Entrée ${fp(entry)} · SL ${fp(sl)} · TP ${fp(tp)} · depuis ${Math.round(ageMin)} min${pl}`;
        }
        return r;
      }
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
