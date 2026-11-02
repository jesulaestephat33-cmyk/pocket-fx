/* Pocket FX - cycle de vie du signal dans le gros panneau :
   BUY NOW / SELL NOW (clignotant) tant que la bougie n'a pas passé l'entrée (~1 min), puis BUY EN COURS / SELL EN COURS
   (fixe, avec le R actuel), puis FIN DE TRADE (TP ou SL touché, WIN / LOSS). Les trades passés sont tracés sur le graphique
   en pointillé de l'entrée jusqu'à la sortie. Un SL collé à l'entrée ou du mauvais côté est signalé comme invalide. */
(function(root){
'use strict';
if(typeof PFXJ === 'undefined' || !PFXJ.finished) return;
const NOW_MIN = 1;                                  // durée du clignotement "NOW" (minutes)
const _setState = root.setState, _updateMarker = root.updateMarker;
if(typeof _setState !== 'function') return;

// on garde la dernière réponse /api/signal et le dernier prix de chaque actif
const lastPx = {};
const _fetch = root.fetch.bind(root);
root.fetch = function(url, o){
  const p = _fetch(url, o);
  try{
    const u = String(url), a = new URL(u, location.href).searchParams.get('asset');
    if(a && u.indexOf('/api/candles') >= 0){
      // dernier prix de l'actif (stocké avant que la page reçoive la réponse)
      return p.then(r => r.clone().json().then(d => { if(Array.isArray(d) && d.length) lastPx[a] = d[d.length-1].close; return r; }).catch(() => r));
    }
  }catch(e){}
  return p;
};
// trade S/R encore ouvert d'un actif, lu directement dans le journal enregistré
function openTrade(asset){
  try{
    const j = JSON.parse(localStorage.getItem('pfx_journal_v1') || '[]');
    const last = j.filter(t => t.src === 'S/R' && t.asset === asset).slice(-1)[0];
    return last && !last.result ? last : null;
  }catch(e){ return null; }
}
const fp = p => Math.abs(p) >= 100 ? (+p).toFixed(2) : (+p).toFixed(4);

// la page appelle setState(data) avec l'objet renvoyé par /api/signal ; on affiche le texte voulu puis on remplace le titre
function render(headline, html, colorState){
  _setState({ state: colorState, message: html, confidence: null });
  const panel = document.getElementById('signalPanel'), st = document.getElementById('signalState');
  if(panel){ panel.classList.remove('alert'); panel.style.removeProperty('--flash-color'); }
  if(st){ st.textContent = headline; st.className = 'signal-state ' + (colorState === 'buy' || colorState === 'sell' ? colorState : 'wait'); }
}
function rLive(asset, side, entry, sl){
  const px = lastPx[asset], risk = Math.abs(entry - sl);
  if(!px || !risk) return '';
  const rr = (px - entry) * (side === 'BUY' ? 1 : -1) / risk;
  return ` · en cours : <b style="color:${rr >= 0 ? '#29D398' : '#FF5C72'}">${rr >= 0 ? '+' : ''}${rr.toFixed(2)}R</b>`;
}
root.setState = function(data){
  if(!data || typeof data !== 'object') return _setState.apply(this, arguments);
  const kind = data.state, asset = currentAsset.id;
  if(kind === 'buy' || kind === 'sell'){
    const side = kind.toUpperCase();
    const t = PFXJ.finished(asset, side, data.level);
    if(t){
      const win = t.result === 'win', exp = t.result === 'expired', out = win ? t.tp : t.sl;
      render('Fin de trade', exp
        ? `<b style="color:#F5B841">${t.side} ${t.asset} expiré</b> · ni TP ni SL touché en ${PFXJ.maxMin} min · entrée ${fp(t.entry)} · en attente d'un nouveau signal`
        : `<b style="color:${win ? '#29D398' : '#FF5C72'}">${t.side} ${t.asset} · ${win ? 'TP touché · WIN +' + t.r.toFixed(2) + 'R' : 'SL touché · LOSS -1R'}</b> · entrée ${fp(t.entry)} → sortie ${fp(out)} · en attente d'un nouveau signal`, 'wait');
      return;
    }
    // si ce trade est déjà ouvert dans le journal (signal ré-émis par le moteur), on affiche ton trade, pas le nouveau signal
    const ot = openTrade(asset), same = !!(ot && ot.side === side);
    if(same || data.signal_time){
      const ageMin = (Date.now()/1000 - (same ? ot.t0 : data.signal_time)) / 60;
      const entry = same ? +ot.entry : +(data.entry || data.price_exness), sl = same ? +ot.sl : +data.sl, tp = same ? +ot.tp : +data.tp;
      const wrong = kind === 'buy' ? !(sl < entry && entry < tp) : !(tp < entry && entry < sl);
      const bad = wrong || (entry > 0 && sl > 0 && Math.abs(entry - sl) < entry * 0.0002);
      if(bad){
        render('SIGNAL INVALIDE', `<b style="color:#F5B841">${wrong ? 'Signal incohérent : SL/TP du mauvais côté du prix' : "SL trop proche de l'entrée (" + fp(Math.abs(entry - sl)) + ")"}</b> · ne pas prendre`, 'wait');
        return;
      }
      if(ageMin >= NOW_MIN){
        render(side + ' EN COURS', `Entrée ${fp(entry)} · SL ${fp(sl)} · TP ${fp(tp)} · depuis ${Math.round(ageMin)} min${rLive(asset, side, entry, sl)}`, kind);
        return;
      }
    }
  }
  // le moteur est repassé en attente (redémarrage, tendance inversée...) mais un trade S/R est toujours ouvert dans le journal
  if(kind === 'wait' && !/hors ligne/.test(String(data.message || ''))){
    const o = openTrade(asset);
    if(o){
      render(o.side + ' EN COURS', `Entrée ${fp(o.entry)} · SL ${fp(o.sl)} · TP ${fp(o.tp)} · depuis ${Math.round((Date.now()/1000 - o.t0) / 60)} min${rLive(asset, o.side, o.entry, o.sl)}`, o.side.toLowerCase());
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

/* ---- trades passés : ligne pointillée de l'entrée à la sortie ---- */
const TFSEC = { M1:60, M5:300, M15:900, H1:3600, H4:14400 };
let histSeries = [], histKey = '', openLines = [];
function clearHist(){
  histSeries.forEach(x => { try{ chart.removeSeries(x); }catch(e){} }); histSeries = [];
  openLines.forEach(l => { try{ candleSeries.removePriceLine(l); }catch(e){} }); openLines = [];
}
function drawHist(){
  try{
    if(typeof chart === 'undefined' || !chart || typeof LightweightCharts === 'undefined') return;
    const raw = localStorage.getItem('pfx_journal_v1') || '[]';
    const key = currentAsset.id + '|' + currentTf + '|' + raw.length + '|' + raw.slice(-80);
    if(key === histKey) return; histKey = key;
    clearHist();
    const tf = TFSEC[currentTf] || 300, now = Math.floor(Date.now()/1000);
    JSON.parse(raw).filter(t => t.asset === currentAsset.id && t.result !== 'expired').slice(-40).forEach(t => {
      const open = !t.result, win = t.result === 'win';
      const sh = (typeof timeShift !== 'undefined' ? timeShift : 0);   // même décalage horaire que les bougies de la page
      const x0 = Math.floor(t.t0 / tf) * tf + sh;
      let x1 = Math.floor((open ? now : t.t1) / tf) * tf + sh; if(x1 <= x0) x1 = x0 + tf;
      const y1 = open ? t.entry : (win ? t.tp : t.sl);
      const color = open ? '#F5B841' : (win ? '#29D398' : '#FF5C72');
      const ser = chart.addLineSeries({ color, lineWidth:2, lineStyle: LightweightCharts.LineStyle.Dotted,
        priceLineVisible:false, lastValueVisible:false, crosshairMarkerVisible:false });
      ser.setData([{ time:x0, value:t.entry }, { time:x1, value:y1 }]);
      if(!open) ser.setMarkers([{ time:x1, position:'inBar', color, shape:'circle', text: t.side + (win ? ' TP +' + t.r.toFixed(1) + 'R' : ' SL -1R') }]);
      histSeries.push(ser);
      if(open && t.src === 'S/R'){   // trade en cours : SL et TP bien visibles sur le graphique
        const mk = (price, c, title) => openLines.push(candleSeries.createPriceLine({ price, color:c, lineWidth:1,
          lineStyle: LightweightCharts.LineStyle.Dotted, axisLabelVisible:true, title }));
        mk(t.sl, '#FF5C72', 'SL'); mk(t.tp, '#29D398', 'TP');
        // série invisible : force l'échelle du graphique à inclure SL et TP
        const fit = chart.addLineSeries({ color:'rgba(0,0,0,0)', lineWidth:1, priceLineVisible:false, lastValueVisible:false, crosshairMarkerVisible:false });
        fit.setData([{ time:x0, value:t.tp }, { time:x1, value:t.sl }]);
        histSeries.push(fit);
      }
    });
  }catch(e){}
}
setInterval(drawHist, 3000); setTimeout(drawHist, 2000);
})(window);
