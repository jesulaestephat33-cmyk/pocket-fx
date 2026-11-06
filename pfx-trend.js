/* Pocket FX - Tendance M15 (EXPERIMENTAL) : repli dans la tendance (EMA20/EMA50 + RSI), reprise, puis stop suiveur de 2 ATR.
   Pas de TP fixe : le stop suit le prix et on laisse courir (max 100 bougies = 25 h). Valide en backtest : +0.07R/trade net du spread. */
(function(root){
'use strict';
const M = 2.0, MAXHOLD = 100;

function ema(v, n){ const k = 2/(n+1); let e = v[0]; const out = [e]; for(let i=1;i<v.length;i++){ e = v[i]*k + e*(1-k); out.push(e); } return out; }
function rsiArr(cl){
  const out = new Array(cl.length).fill(50); let g = 0, l = 0;
  for(let i=1;i<cl.length;i++){
    const d = cl[i]-cl[i-1];
    if(i <= 14){ g += Math.max(d,0)/14; l += Math.max(-d,0)/14; } else { g = (g*13 + Math.max(d,0))/14; l = (l*13 + Math.max(-d,0))/14; }
    out[i] = l === 0 ? 100 : 100 - 100/(1 + g/l);
  }
  return out;
}
function atrAt(c, j){ if(j < 14) return 0; let s = 0; for(let k=j-13;k<=j;k++) s += c[k].high - c[k].low; return s/14; }

// c = bougies M15 FERMEES seulement. Signal sur la derniere : { side, entry, atr, key } ou null.
function trendSignal(c){
  if(!Array.isArray(c) || c.length < 70) return null;
  const i = c.length-1, px = c[i].close, a = atrAt(c, i); if(!(a > 0)) return null;
  const cl = c.map(b => b.close), e20 = ema(cl,20), e50 = ema(cl,50), r = rsiArr(cl);
  if(c[i].time - c[i-30].time > 30*900*2) return null;                        // trou de donnees (week-end, pause)
  let side = null;
  if(e20[i] > e50[i] && px > e50[i] && r[i-1] < 40 && px > c[i-1].high) side = 'BUY';
  else if(e20[i] < e50[i] && px < e50[i] && r[i-1] > 60 && px < c[i-1].low) side = 'SELL';
  return side ? { side, entry:px, atr:a, key:side + '|' + c[i].time } : null;
}

// Rejoue le trade sur les bougies fermees apres l'entree. Retourne { stop, peak, closed, exit, r, t1, why }.
function replay(t, c){
  const s = t.side === 'BUY' ? 1 : -1, risk = M*t.atr;
  let idx = -1; for(let k=0;k<c.length;k++) if(c[k].time === t.barTime){ idx = k; break; }
  let stop = t.entry - s*risk, peak = t.entry;
  if(idx < 0) return { stop, peak, closed:false };
  for(let j=idx+1; j<c.length && j<=idx+MAXHOLD; j++){
    if(s*(( s>0 ? c[j].low : c[j].high) - stop) <= 0){
      const ex = s*(c[j].open - stop) > 0 ? stop : c[j].open;
      return { stop, peak, closed:true, exit:ex, r:(ex - t.entry)*s/risk, t1:c[j].time, why:'stop' };
    }
    peak = s>0 ? Math.max(peak, c[j].close) : Math.min(peak, c[j].close);
    const a = atrAt(c, j); if(a > 0) stop = s>0 ? Math.max(stop, peak - M*a) : Math.min(stop, peak + M*a);
    if(j === idx+MAXHOLD) return { stop, peak, closed:true, exit:c[j].close, r:(c[j].close - t.entry)*s/risk, t1:c[j].time, why:'temps' };
  }
  return { stop, peak, closed:false };
}

const api = { trendSignal, replay, M, MAXHOLD };
root.PFXT = api;
if(typeof module !== 'undefined' && module.exports) module.exports = api;
if(typeof document === 'undefined') return;

/* ============================== INTERFACE ============================== */
const BACK = (typeof BACKEND !== 'undefined') ? BACKEND : 'http://localhost:8000';
const IDS = ['GER40','CAC40','SPX500','NAS100','US30','XAUUSD','USOIL','BTCUSD'];
const KEY = 'pfx_trend_v1';
let on = false, timer = null, audio = null, lastScan = '', lastPx = {}, trades = [];
try{ trades = JSON.parse(localStorage.getItem(KEY) || '[]'); }catch(e){}
const save = () => { try{ localStorage.setItem(KEY, JSON.stringify(trades.slice(-300))); }catch(e){} };

function beep(){
  try{
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    [740, 988].forEach((f,i)=>{ const o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = f; o.connect(g); g.connect(audio.destination);
      const t = audio.currentTime + i*0.15; g.gain.setValueAtTime(0.0001,t); g.gain.exponentialRampToValueAtTime(0.3,t+0.02); g.gain.exponentialRampToValueAtTime(0.0001,t+0.14);
      o.start(t); o.stop(t+0.15); });
  }catch(e){}
}
const fp = p => Math.abs(p) >= 100 ? (+p).toFixed(2) : (+p).toFixed(4);
const fmtT = s => { const d = new Date(s*1000); return d.toLocaleDateString('fr-FR',{day:'2-digit',month:'2-digit'}) + ' ' + d.toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'}); };
const rTxt = r => (r >= 0 ? '+' : '') + r.toFixed(2) + 'R';
const rCol = r => r >= 0 ? '#29D398' : '#FF5C72';

function render(){
  const el = document.getElementById('pfxTrend'); if(!el) return;
  el.style.display = 'block';
  const open = trades.filter(t => !t.closed), done = trades.filter(t => t.closed);
  const wins = done.filter(t => t.r > 0).length, sum = done.reduce((a,t) => a + t.r, 0);
  const openRows = open.map(t => {
    const s = t.side === 'BUY' ? 1 : -1, risk = M*t.atr, px = lastPx[t.asset];
    const r = px ? (px - t.entry)*s/risk : null;
    return `<div style="margin-top:4px"><b style="color:${t.side==='BUY'?'#29D398':'#FF5C72'}">${t.asset} ${t.side} EN COURS</b> · entrée ${fp(t.entry)} · stop suiveur <b>${fp(t.stop)}</b>` +
      (r === null ? '' : ` · <b style="color:${rCol(r)}">${rTxt(r)}</b>`) + ` · depuis ${fmtT(t.t0)}</div>`;
  }).join('');
  const doneRows = done.slice().reverse().slice(0,8).map(t =>
    `<div style="margin-top:3px;color:#8892A6">${fmtT(t.t1)} · ${t.asset} ${t.side} · sortie ${fp(t.exit)} · <b style="color:${rCol(t.r)}">${rTxt(t.r)}</b>${t.why === 'temps' ? ' (temps max)' : ''}</div>`).join('');
  el.innerHTML = `<b>Tendance M15</b> <span style="color:#F5B841">expérimental</span> · ${IDS.length} actifs · scan ${lastScan || '—'}` +
    ` · terminés ${done.length} · réussite ${done.length ? Math.round(wins/done.length*100) + '%' : '-'} · total <b style="color:${rCol(sum)}">${rTxt(sum)}</b> (moyenne ${done.length ? rTxt(sum/done.length) : '-'})` +
    (openRows || `<div style="margin-top:4px;color:#8892A6">aucun trade en cours, en attente d'un repli dans la tendance</div>`) + (doneRows ? `<div style="margin-top:8px;color:#8892A6">Derniers trades terminés :</div>` + doneRows : '');
}

async function scan(){
  if(!on) return;
  const now = Math.floor(Date.now()/1000);
  await Promise.all(IDS.map(async id => {
    let c; try{ c = await (await fetch(`${BACK}/api/candles?asset=${id}&tf=M15&count=300`)).json(); }catch(e){ return; }
    if(!Array.isArray(c) || c.length < 120) return;
    lastPx[id] = c[c.length-1].close;
    const closed = c.slice(0, -1);                                         // la derniere bougie est en formation
    trades.filter(t => !t.closed && t.asset === id).forEach(t => {         // met a jour le stop suiveur / detecte la sortie
      const r = replay(t, closed); t.stop = r.stop;
      if(r.closed){ t.closed = true; t.exit = r.exit; t.r = r.r; t.t1 = r.t1; t.why = r.why; beep(); }
    });
    if(now - c[c.length-1].time > 1800) return;                            // marche ferme / flux gelé
    if(trades.some(t => !t.closed && t.asset === id)) return;              // un trade a la fois par actif
    const s = trendSignal(closed); if(!s) return;
    if(trades.some(t => t.asset === id && t.key === s.key)) return;        // un seul trade par bougie de signal
    if(Math.abs(lastPx[id] - s.entry) > 0.5*s.atr) return;                 // deja parti
    const barTime = closed[closed.length-1].time, sgn = s.side === 'BUY' ? 1 : -1;
    trades.push({ asset:id, side:s.side, entry:s.entry, atr:s.atr, key:s.key, barTime, t0:now, stop:s.entry - sgn*M*s.atr, closed:false });
    beep();
  }));
  save(); lastScan = new Date().toLocaleTimeString('fr-FR'); render();
}

function init(){
  const bar = document.getElementById('pfxBar'); if(!bar) return;
  const b = document.createElement('button'); b.textContent = 'Tendance M15';
  b.title = 'EXPERIMENTAL : repli dans la tendance en M15, stop suiveur 2 ATR, sans TP fixe (jusqu a 25 h). Surveille les 8 actifs.';
  b.addEventListener('click', () => {
    on = !on; b.classList.toggle('on', on);
    clearInterval(timer); const el = document.getElementById('pfxTrend');
    if(on){ beep(); scan(); timer = setInterval(scan, 30000); } else if(el) el.style.display = 'none';
  });
  const scanBtn = bar.querySelector('button.scan'); bar.insertBefore(b, scanBtn || null);
  const box = document.createElement('div'); box.id = 'pfxTrend';
  box.style.cssText = "display:none;width:100%;margin-top:4px;padding:10px 14px;border:1px solid #232838;border-radius:10px;background:#12161F;color:#F0F2F6;font:12px 'JetBrains Mono',monospace";
  bar.appendChild(box);
  setInterval(() => { if(on) render(); }, 5000);
}
init();
})(typeof window !== 'undefined' ? window : globalThis);
