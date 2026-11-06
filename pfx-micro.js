/* Pocket FX - Micro scalp : tendance M1 (EMA 20 > EMA 50), petit repli, puis reprise de la tendance.
   SL derrière le creux (ou sommet) du repli, TP = 1.5 x le risque. Scanne les 8 actifs. Expire après 15 min. */
(function(root){
'use strict';
const RR = 1.5, MAX_MIN = 15;

function ema(v, n){ const k = 2/(n+1); let e = v[0]; const out = [e]; for(let i=1;i<v.length;i++){ e = v[i]*k + e*(1-k); out.push(e); } return out; }

// c = bougies M1 (la dernière est en cours de formation). Retourne { side, entry, sl, tp, key } ou null.
function microSignal(c){
  if(!Array.isArray(c) || c.length < 70) return null;
  const n = c.length, i = n - 2;                       // i = dernière bougie fermée
  const closes = c.map(b => b.close), e20 = ema(closes, 20), e50 = ema(closes, 50);
  let atr = 0; for(let k = i-13; k <= i; k++) atr += c[k].high - c[k].low; atr /= 14;
  if(!(atr > 0)) return null;
  const px = c[n-1].close, bar = c[i], prev = c[i-1];
  const up = e20[i] > e50[i] && bar.close > e50[i] && (e20[i] - e50[i]) >= 0.25*atr;
  const dn = e20[i] < e50[i] && bar.close < e50[i] && (e50[i] - e20[i]) >= 0.25*atr;
  if(!up && !dn) return null;
  const from = i - 20;
  if(up){
    let ih = from; for(let k = from; k <= i; k++) if(c[k].high >= c[ih].high) ih = k;       // dernier sommet
    let ip = ih + 1; if(ip > i) return null;
    for(let k = ih + 1; k <= i; k++) if(c[k].low <= c[ip].low) ip = k;                       // creux du repli
    const P = c[ip].low, depth = c[ih].high - P;
    if(depth < 0.8*atr || ip < i - 6 || P < e50[ip] - 0.2*atr) return null;                 // vrai repli, récent, qui tient la tendance
    if(!(bar.close > prev.high && bar.close > bar.open && bar.close > e20[i])) return null;  // reprise confirmée
    if(px - bar.close > 0.5*atr) return null;                                                // pas déjà parti
    const sl = Math.min(P - 0.25*atr, px - atr), risk = px - sl;
    if(risk > 3*atr) return null;
    return { side:'BUY', entry:px, sl, tp: px + RR*risk, key:'BUY|' + c[ip].time, atr };
  }
  let il = from; for(let k = from; k <= i; k++) if(c[k].low <= c[il].low) il = k;            // dernier creux
  let ip = il + 1; if(ip > i) return null;
  for(let k = il + 1; k <= i; k++) if(c[k].high >= c[ip].high) ip = k;                       // sommet du rebond
  const P = c[ip].high, depth = P - c[il].low;
  if(depth < 0.8*atr || ip < i - 6 || P > e50[ip] + 0.2*atr) return null;
  if(!(bar.close < prev.low && bar.close < bar.open && bar.close < e20[i])) return null;
  if(bar.close - px > 0.5*atr) return null;
  const sl = Math.max(P + 0.25*atr, px + atr), risk = sl - px;
  if(risk > 3*atr) return null;
  return { side:'SELL', entry:px, sl, tp: px - RR*risk, key:'SELL|' + c[ip].time, atr };
}

const api = { microSignal, RR, MAX_MIN };
root.PFXM = api;
if(typeof module !== 'undefined' && module.exports) module.exports = api;
if(typeof document === 'undefined') return;

/* ============================== INTERFACE ============================== */
const BACK = (typeof BACKEND !== 'undefined') ? BACKEND : 'http://localhost:8000';
const IDS = ['GER40','CAC40','SPX500','NAS100','US30','XAUUSD','USOIL','BTCUSD'];
let on = false, timer = null, audio = null, seen = {}, lastScan = '', lastPx = {};
try{ seen = JSON.parse(localStorage.getItem('pfx_micro_seen') || '{}'); }catch(e){}

function beep(){
  try{
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    [880, 1175].forEach((f,i)=>{ const o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = f; o.connect(g); g.connect(audio.destination);
      const t = audio.currentTime + i*0.15; g.gain.setValueAtTime(0.0001,t); g.gain.exponentialRampToValueAtTime(0.3,t+0.02); g.gain.exponentialRampToValueAtTime(0.0001,t+0.14);
      o.start(t); o.stop(t+0.15); });
  }catch(e){}
}
const fp = p => Math.abs(p) >= 100 ? (+p).toFixed(2) : (+p).toFixed(4);

function openTrades(){
  try{ return JSON.parse(localStorage.getItem('pfx_journal_v1') || '[]').filter(t => t.src === 'MICRO' && !t.result); }catch(e){ return []; }
}
function render(){
  const el = document.getElementById('pfxMicro'); if(!el) return;
  el.style.display = 'block';
  const rows = openTrades().map(t => {
    const px = lastPx[t.asset], risk = Math.abs(t.entry - t.sl);
    const r = px && risk ? (px - t.entry) * (t.side === 'BUY' ? 1 : -1) / risk : null;
    const col = t.side === 'BUY' ? '#29D398' : '#FF5C72';
    return `<div style="margin-top:4px"><b style="color:${col}">${t.asset} ${t.side} EN COURS</b> · entrée ${fp(t.entry)} · SL ${fp(t.sl)} · TP ${fp(t.tp)}` +
      (r === null ? '' : ` · <b style="color:${r >= 0 ? '#29D398' : '#FF5C72'}">${r >= 0 ? '+' : ''}${r.toFixed(2)}R</b>`) +
      ` · depuis ${Math.round((Date.now()/1000 - t.t0)/60)} min</div>`;
  }).join('');
  el.innerHTML = `<b>Micro scalp</b> · ${IDS.length} actifs surveillés · dernier scan ${lastScan || '—'}` + (rows || `<div style="margin-top:4px;color:#8892A6">aucun trade en cours, en attente d'une reprise de tendance</div>`);
}

async function scan(){
  if(!on) return;
  const now = Math.floor(Date.now()/1000);
  await Promise.all(IDS.map(async id => {
    let c; try{ c = await (await fetch(`${BACK}/api/candles?asset=${id}&tf=M1&count=120`)).json(); }catch(e){ return; }
    if(!Array.isArray(c) || c.length < 70) return;
    lastPx[id] = c[c.length-1].close;
    if(now - c[c.length-1].time > 150) return;                       // marché fermé / flux gelé
    const s = microSignal(c); if(!s) return;
    const k = id + '|' + s.key; if(seen[k]) return;                  // un seul signal par repli
    if(openTrades().some(t => t.asset === id)) return;               // un trade micro à la fois par actif
    seen[k] = now;
    Object.keys(seen).forEach(x => { if(now - seen[x] > 6*3600) delete seen[x]; });
    try{ localStorage.setItem('pfx_micro_seen', JSON.stringify(seen)); }catch(e){}
    PFXJ.record({ src:'MICRO', asset:id, tf:'M1', side:s.side, entry:s.entry, sl:s.sl, tp:s.tp, lvl:s.key, t0:now, maxMin:MAX_MIN });
    beep();
  }));
  lastScan = new Date().toLocaleTimeString('fr-FR');
  render();
}

function init(){
  const bar = document.getElementById('pfxBar'); if(!bar || typeof PFXJ === 'undefined') return;
  const b = document.createElement('button'); b.textContent = 'Micro scalp';
  b.title = 'Tendance M1, petit repli puis reprise : SL derrière le repli, TP = 1.5 x le risque. Surveille les 8 actifs.';
  b.addEventListener('click', () => {
    on = !on; b.classList.toggle('on', on);
    clearInterval(timer); const el = document.getElementById('pfxMicro');
    if(on){ beep(); scan(); timer = setInterval(scan, 10000); } else if(el) el.style.display = 'none';
  });
  const scanBtn = bar.querySelector('button.scan'); bar.insertBefore(b, scanBtn || null);
  const box = document.createElement('div'); box.id = 'pfxMicro';
  box.style.cssText = "display:none;width:100%;margin-top:4px;padding:10px 14px;border:1px solid #232838;border-radius:10px;background:#12161F;color:#F0F2F6;font:12px 'JetBrains Mono',monospace";
  bar.appendChild(box);
  setInterval(() => { if(on) render(); }, 3000);
}
init();
})(typeof window !== 'undefined' ? window : globalThis);
