/* Pocket FX - Swing journalier : RSI2, Double 7, IBS, Tendance 12 mois (long seulement, au-dessus de la SMA200 journaliere).
   Regles publiees (Connors, Antonacci), non optimisees. Test 5 ans sur NAS100/SPX500/US30/GER40 : a valider en demo avant tout argent reel. */
(function(root){
'use strict';
const NAMES = ['RSI2','DOUBLE7','IBS','TENDANCE12'];
const LABEL = { RSI2:'RSI 2', DOUBLE7:'Double 7', IBS:'IBS', TENDANCE12:'Tendance 12 mois' };
const HOW = { RSI2:'sort quand le cours passe au-dessus de la SMA 5', DOUBLE7:'sort sur un plus haut de 7 jours', IBS:'sort quand le cours depasse le plus haut de la veille', TENDANCE12:'reste tant que le cours > cours d il y a 12 mois' };

// c = bougies journalieres (la plus ancienne d abord). Retourne, par moteur, un tableau 0/1 : 1 = en position apres la cloture de la bougie.
function engines(c){
  const n = c.length, cl = c.map(b => b.close), P = {}; NAMES.forEach(k => P[k] = new Array(n).fill(0));
  let g = 0, lo = 0; const st = { RSI2:0, DOUBLE7:0, IBS:0 };
  const sma = (i,k) => { let s = 0; for(let j=i-k+1;j<=i;j++) s += cl[j]; return s/k; };
  for(let i=1;i<n;i++){
    const d = cl[i]-cl[i-1];
    if(i <= 2){ g += Math.max(d,0)/2; lo += Math.max(-d,0)/2; } else { g = (g+Math.max(d,0))/2; lo = (lo+Math.max(-d,0))/2; }
    const r2 = lo === 0 ? 100 : 100 - 100/(1+g/lo);
    if(i < 252) continue;
    const s200 = sma(i,200), up = cl[i] > s200, s5 = sma(i,5);
    let mx = -Infinity, mn = Infinity; for(let j=i-6;j<=i;j++){ mx = Math.max(mx, cl[j]); mn = Math.min(mn, cl[j]); }
    const rg = c[i].high - c[i].low, ibs = rg > 0 ? (cl[i]-c[i].low)/rg : 0.5;
    if(st.RSI2) st.RSI2 = cl[i] > s5 ? 0 : 1; else if(r2 < 10 && up) st.RSI2 = 1;
    if(st.DOUBLE7) st.DOUBLE7 = cl[i] >= mx ? 0 : 1; else if(cl[i] <= mn && up) st.DOUBLE7 = 1;
    if(st.IBS) st.IBS = cl[i] > c[i-1].high ? 0 : 1; else if(ibs < 0.2 && up) st.IBS = 1;
    P.RSI2[i] = st.RSI2; P.DOUBLE7[i] = st.DOUBLE7; P.IBS[i] = st.IBS; P.TENDANCE12[i] = (cl[i] > cl[i-252] && up) ? 1 : 0;
  }
  return P;
}

// Etat de chaque moteur sur la derniere bougie : { name, on, event:'ENTREE'|'SORTIE'|null, since (time), price }
function status(c){
  if(!Array.isArray(c) || c.length < 270) return null;
  const P = engines(c), i = c.length-1;
  return NAMES.map(k => {
    const p = P[k], on = p[i] === 1; let j = i; if(on) while(j > 0 && p[j-1] === 1) j--;
    return { name:k, on, event: on && p[i-1] === 0 ? 'ENTREE' : (!on && p[i-1] === 1 ? 'SORTIE' : null), since: on ? c[j].time : null, price: c[j].close };
  });
}

const api = { engines, status, NAMES };
root.PFXS = api;
if(typeof module !== 'undefined' && module.exports) module.exports = api;
if(typeof document === 'undefined') return;

/* ============================== INTERFACE ============================== */
const BACK = (typeof BACKEND !== 'undefined') ? BACKEND : 'http://localhost:8000';
const IDS = ['NAS100','SPX500','US30','GER40'];
const KEY = 'pfx_swing_v1';
let on = false, timer = null, audio = null, lastScan = '', data = {}, seen = {};
try{ seen = JSON.parse(localStorage.getItem(KEY) || '{}'); }catch(e){}
const saveSeen = () => { try{ localStorage.setItem(KEY, JSON.stringify(seen)); }catch(e){} };
function beep(){
  try{
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    [660, 880].forEach((f,i)=>{ const o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = f; o.connect(g); g.connect(audio.destination);
      const t = audio.currentTime + i*0.18; g.gain.setValueAtTime(0.0001,t); g.gain.exponentialRampToValueAtTime(0.3,t+0.02); g.gain.exponentialRampToValueAtTime(0.0001,t+0.16);
      o.start(t); o.stop(t+0.17); });
  }catch(e){}
}
const fp = p => Math.abs(p) >= 100 ? (+p).toFixed(2) : (+p).toFixed(4);
const fd = s => new Date(s*1000).toLocaleDateString('fr-FR', { day:'2-digit', month:'2-digit', timeZone:'UTC' });
const GREEN = '#29D398', RED = '#FF5C72', GREY = '#8892A6', AMBER = '#F5B841';

function render(){
  const el = document.getElementById('pfxSwing'); if(!el) return; el.style.display = 'block';
  const rows = IDS.map(id => {
    const d = data[id]; if(!d) return `<div style="margin-top:8px;color:${GREY}">${id} : pas de données</div>`;
    const chips = NAMES.map((k, n) => {
      const a = d.conf[n], b = d.prov ? d.prov[n] : null; let txt, col;
      if(a.event) { txt = a.event === 'ENTREE' ? 'ACHETER' : 'SORTIR'; col = a.event === 'ENTREE' ? GREEN : RED; }
      else if(a.on) { txt = 'en position depuis ' + fd(a.since); col = GREEN; }
      else { txt = 'hors position'; col = GREY; }
      let prov = '';
      if(b && b.event && !a.event) prov = ` <span style="color:${AMBER}">· provisoire : ${b.event === 'ENTREE' ? 'achat probable' : 'sortie probable'} ce soir</span>`;
      return `<div style="margin-top:3px"><span style="color:${GREY}">${LABEL[k]}</span> · <b style="color:${col}">${txt}</b>${prov}</div>`;
    }).join('');
    const nOn = d.conf.filter(x => x.on).length;
    return `<div style="margin-top:10px;padding-top:8px;border-top:1px solid #232838"><b>${id}</b> · dernier cours ${fp(d.px)} · clôture confirmée du ${fd(d.lastClosed)} · <b style="color:${nOn ? GREEN : GREY}">${nOn} moteur(s) en position</b>${chips}</div>`;
  }).join('');
  el.innerHTML = `<b>Swing journalier</b> <span style="color:${AMBER}">à valider en démo</span> · vérifie 1 fois par jour après la clôture · mis à jour ${lastScan || '—'}` +
    `<div style="margin-top:4px;color:${GREY}">Achat seulement (long). Chaque moteur a sa propre sortie. Tu passes l'ordre toi-même chez ton broker.</div>` + rows;
}

async function scan(){
  if(!on) return; const now = Math.floor(Date.now()/1000); let fresh = false;
  await Promise.all(IDS.map(async id => {
    let c; try{ c = await (await fetch(`${BACK}/api/candles?asset=${id}&tf=D1&count=420`)).json(); }catch(e){ return; }
    if(!Array.isArray(c) || c.length < 280) return;
    const forming = now - c[c.length-1].time < 86400, closed = forming ? c.slice(0, -1) : c;
    const conf = status(closed); if(!conf) return;
    data[id] = { conf, prov: forming ? status(c) : null, px:c[c.length-1].close, lastClosed:closed[closed.length-1].time };
    conf.forEach(x => { if(!x.event) return; const k = id + '|' + x.name + '|' + x.event + '|' + data[id].lastClosed; if(!seen[k]){ seen[k] = 1; fresh = true; } });
  }));
  if(fresh){ beep(); saveSeen(); }
  lastScan = new Date().toLocaleTimeString('fr-FR'); render();
}

function init(){
  const bar = document.getElementById('pfxBar'); if(!bar) return;
  const b = document.createElement('button'); b.textContent = 'Swing jour';
  b.title = 'Swing journalier (long seulement) : RSI2, Double 7, IBS, Tendance 12 mois sur NAS100, SPX500, US30, GER40. A verifier 1 fois par jour apres la cloture.';
  b.addEventListener('click', () => {
    on = !on; b.classList.toggle('on', on); clearInterval(timer); const el = document.getElementById('pfxSwing');
    if(on){ scan(); timer = setInterval(scan, 600000); } else if(el) el.style.display = 'none';
  });
  const scanBtn = bar.querySelector('button.scan'); bar.insertBefore(b, scanBtn || null);
  const box = document.createElement('div'); box.id = 'pfxSwing';
  box.style.cssText = "display:none;width:100%;margin-top:4px;padding:10px 14px;border:1px solid #232838;border-radius:10px;background:#12161F;color:#F0F2F6;font:12px 'JetBrains Mono',monospace";
  bar.appendChild(box);
}
init();
})(typeof window !== 'undefined' ? window : globalThis);
