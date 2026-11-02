/* Pocket FX - Signal Fibonacci : BUY/SELL quand le prix revient dans la zone 50-78.6% du dernier mouvement
   avec une bougie de rejet. SL = 100% du Fib (marge 2 pips incluse), TP = 2R. */
(function(root){
'use strict';
const P = (typeof PFX !== 'undefined') ? PFX : (typeof require !== 'undefined' ? require('./pfx-structure.js') : null);
if(!P) return;
const RR = 2;

function rejection(bar, side){
  const range = bar.high - bar.low; if(range <= 0) return false;
  const lowW = Math.min(bar.open, bar.close) - bar.low;
  const upW  = bar.high - Math.max(bar.open, bar.close);
  return side === 'BUY' ? (bar.close > bar.open && lowW / range >= 0.35)
                        : (bar.close < bar.open && upW  / range >= 0.35);
}

function fibSignal(c, asset, tf){
  const r = P.analyze(c, asset, tf, { fibMode:'last' });
  const f = r.fib;
  if(!f || !f.levels) return { state:'wait', why: f && f.waiting ? 'Fib : ' + f.waiting : 'structure indéterminée', r };
  const side = f.dir === 'up' ? 'BUY' : 'SELL';
  const n = c.length, price = c[n-1].close;
  const [zLo, zHi] = f.zone;
  const invalid = side==='BUY' ? price <= f.p100 : price >= f.p100;
  if(invalid) return { state:'wait', why:'Fib invalidé (le prix a cassé le 100%)', r, f, side };
  const retr = f.retrace;
  if(!(price >= zLo && price <= zHi)){
    const why = retr < 0.5 ? `retracement ${(retr*100).toFixed(0)}% (zone = 50–78.6%)` : `retracement ${(retr*100).toFixed(0)}% (déjà trop profond)`;
    return { state:'wait', why, r, f, side };
  }
  let rej = false;
  for(let k = n-4; k <= n-2; k++){
    if(k < 0) continue;
    const b = c[k];
    if(b.low <= zHi && b.high >= zLo && rejection(b, side)){ rej = true; break; }
  }
  if(!rej) return { state:'approach', why:`prix dans la zone Fib, en attente d'une bougie de rejet`, r, f, side };
  const entry = price, sl = f.p100, risk = Math.abs(entry - sl);
  if(risk <= 0) return { state:'wait', why:'risque nul', r, f, side };
  const tp = side==='BUY' ? entry + RR*risk : entry - RR*risk;
  return { state:'signal', side, entry, sl, tp, risk, r, f, key: asset+'|'+tf+'|'+f.a.time+'|'+f.b.time+'|'+side };
}

const api = { fibSignal, rejection, RR };
P.fibSignal = fibSignal;
if(typeof module !== 'undefined' && module.exports) module.exports = api;
if(typeof document === 'undefined') return;

/* ============================== INTERFACE ============================== */
const BACK = (typeof BACKEND !== 'undefined') ? BACKEND : 'http://localhost:8000';
let on = false, timer = null, active = {}, lines = [], audio = null;

function beep(){
  try{
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    [660, 990].forEach((f,i)=>{ const o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = f; o.connect(g); g.connect(audio.destination);
      const t = audio.currentTime + i*0.2; g.gain.setValueAtTime(0.0001,t); g.gain.exponentialRampToValueAtTime(0.3,t+0.02); g.gain.exponentialRampToValueAtTime(0.0001,t+0.18);
      o.start(t); o.stop(t+0.19); });
  }catch(e){}
}
const fmt = p => Math.abs(p) >= 100 ? p.toFixed(2) : p.toFixed(4);

function clearLines(){ lines.forEach(l => { try{ candleSeries.removePriceLine(l); }catch(e){} }); lines = []; }
function drawLines(a){
  clearLines();
  const mk = (price, color, title) => lines.push(candleSeries.createPriceLine({ price, color, lineWidth:2, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible:true, title }));
  mk(a.entry, '#F0F2F6', a.side+' entrée'); mk(a.sl, '#FF5C72', 'SL'); mk(a.tp, '#29D398', 'TP');
}

function show(html, color){
  const el = document.getElementById('pfxFibSig'); if(!el) return;
  el.style.display = 'block'; el.style.borderColor = color || '#232838'; el.innerHTML = html;
}

async function tick(){
  if(!on) return;
  const asset = currentAsset.id, tf = currentTf;
  let c;
  try{ const res = await fetch(`${BACK}/api/candles?asset=${asset}&tf=${tf}&count=1500`); c = await res.json(); }catch(e){ return; }
  if(!Array.isArray(c) || c.length < 30) return;
  const price = c[c.length-1].close;
  const akey = asset + '|' + tf;
  let a = active[akey];

  if(a){
    const hitSL = a.side==='BUY' ? price <= a.sl : price >= a.sl;
    const hitTP = a.side==='BUY' ? price >= a.tp : price <= a.tp;
    if(hitSL || hitTP){
      clearLines(); delete active[akey]; beep();
      show(`<b style="color:#F5B841">CLOSE NOW</b> · ${hitTP ? 'WIN : TP touché (+'+RR+'R)' : 'LOSS : SL touché (-1R)'} · ${a.side} ${asset}`, '#F5B841');
      return;
    }
    drawLines(a);
    const pl = (a.side==='BUY' ? price - a.entry : a.entry - price) / a.risk;
    show(`<b style="color:${a.side==='BUY' ? '#29D398' : '#FF5C72'}">${a.side} NOW</b> · ${asset} ${tf} · entrée ${fmt(a.entry)} · SL ${fmt(a.sl)} · TP ${fmt(a.tp)} · RR ${RR} · en cours : ${pl>=0?'+':''}${pl.toFixed(2)}R`, a.side==='BUY' ? '#29D398' : '#FF5C72');
    return;
  }

  const s = fibSignal(c, asset, tf);
  if(s.state === 'signal'){
    active[akey] = { side:s.side, entry:s.entry, sl:s.sl, tp:s.tp, risk:s.risk, key:s.key };
    if(typeof PFXJ !== 'undefined' && PFXJ.record) PFXJ.record({ src:'FIB', asset, tf, side:s.side, entry:s.entry, sl:s.sl, tp:s.tp });
    drawLines(active[akey]); beep();
    show(`<b style="color:${s.side==='BUY' ? '#29D398' : '#FF5C72'}">${s.side} NOW</b> · ${asset} ${tf} · entrée ${fmt(s.entry)} · SL ${fmt(s.sl)} · TP ${fmt(s.tp)} · RR ${RR}`, s.side==='BUY' ? '#29D398' : '#FF5C72');
  } else {
    clearLines();
    show(`Signal Fib ${asset} ${tf} : <b>${s.state==='approach' ? '⏳ approche' : 'attente'}</b> · ${s.why}`, s.state==='approach' ? '#F5B841' : '#232838');
  }
}

function init(){
  const bar = document.getElementById('pfxBar'); if(!bar) return;
  const b = document.createElement('button'); b.textContent = '🎯 Signal Fib';
  b.title = 'BUY/SELL quand le prix revient dans la zone 50–78.6% du dernier mouvement avec une bougie de rejet. SL = 100%, TP = 2R.';
  b.addEventListener('click', () => {
    on = !on; b.classList.toggle('on', on);
    clearInterval(timer); clearLines();
    const el = document.getElementById('pfxFibSig');
    if(on){ beep(); tick(); timer = setInterval(tick, 5000); } else if(el) el.style.display = 'none';
  });
  const scan = bar.querySelector('button.scan'); bar.insertBefore(b, scan || null);
  const box = document.createElement('div'); box.id = 'pfxFibSig';
  box.style.cssText = "display:none;width:100%;margin-top:4px;padding:10px 14px;border:1px solid #232838;border-radius:10px;background:#12161F;color:#F0F2F6;font:12px 'JetBrains Mono',monospace";
  bar.appendChild(box);
  let last = ''; setInterval(() => { const k = currentAsset.id+'|'+currentTf; if(k !== last){ last = k; clearLines(); if(on) setTimeout(tick, 300); } }, 500);
}
init();
})(typeof window !== 'undefined' ? window : globalThis);
