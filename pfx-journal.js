/* Pocket FX - Journal des signaux : enregistre chaque signal (Fib + support/résistance), détecte WIN / LOSS
   en rejouant les bougies M1 depuis l'entrée, et affiche les statistiques. Données gardées dans ce navigateur. */
(function(root){
'use strict';
const KEY = 'pfx_journal_v1';
const MAX_AGE = 24*3600;
const BACK = (typeof BACKEND !== 'undefined') ? BACKEND : 'http://localhost:8000';

function load(){ try{ return JSON.parse(localStorage.getItem(KEY) || '[]'); }catch(e){ return []; } }
function save(j){ try{ localStorage.setItem(KEY, JSON.stringify(j.slice(-2000))); }catch(e){} }
let journal = load();

function settleTrade(t, candles){
  for(const c of candles){
    if(c.time < t.t0 - 60) continue;
    const hitSL = t.side==='BUY' ? c.low <= t.sl : c.high >= t.sl;
    const hitTP = t.side==='BUY' ? c.high >= t.tp : c.low <= t.tp;
    if(hitSL) return { result:'loss', r:-1, t1:c.time };
    if(hitTP) return { result:'win', r: Math.abs(t.tp - t.entry) / Math.abs(t.entry - t.sl), t1:c.time };
  }
  return null;
}
function stats(j){
  const closed = j.filter(t => t.result==='win' || t.result==='loss');
  const wins = closed.filter(t => t.result==='win').length;
  const sumR = closed.reduce((a,t) => a + (t.r||0), 0);
  return { total:j.length, open:j.filter(t=>!t.result).length, expired:j.filter(t=>t.result==='expired').length,
           closed:closed.length, wins, losses:closed.length-wins,
           winRate: closed.length ? wins/closed.length*100 : 0, sumR, avgR: closed.length ? sumR/closed.length : 0 };
}
const api = { settleTrade, stats };
root.PFXJ = api;
if(typeof module !== 'undefined' && module.exports) module.exports = api;
if(typeof document === 'undefined') return;

function openCount(asset, src){ return journal.some(t => !t.result && t.asset===asset && t.src===src); }
api.record = function(o){
  if(!(o.entry && o.sl && o.tp) || o.entry === o.sl) return;
  if(journal.some(t => !t.result && t.asset===o.asset && t.src===o.src && t.side===o.side && t.tf===o.tf)) return;
  journal.push({ id: Date.now() + '-' + Math.random().toString(36).slice(2,6), src:o.src, asset:o.asset, tf:o.tf||'', side:o.side,
                 entry:o.entry, sl:o.sl, tp:o.tp, t0: Math.floor(Date.now()/1000), result:null, r:null, t1:null });
  save(journal); render();
};

function toast(text, color){
  let b = document.getElementById('pfxToasts');
  if(!b){ b = document.createElement('div'); b.id = 'pfxToasts';
    b.style.cssText = 'position:fixed;bottom:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;max-width:340px'; document.body.appendChild(b); }
  const d = document.createElement('div');
  d.style.cssText = `background:#181D28;border:1px solid ${color};color:#F0F2F6;padding:12px 16px;border-radius:10px;font:12px 'JetBrains Mono',monospace;box-shadow:0 6px 20px rgba(0,0,0,.45)`;
  d.innerHTML = text; b.appendChild(d); setTimeout(()=>d.remove(), 25000); d.addEventListener('click', ()=>d.remove());
  try{ const a = new (root.AudioContext||root.webkitAudioContext)(); const o = a.createOscillator(), g = a.createGain(); o.frequency.value = color==='#29D398' ? 1046 : 330; o.connect(g); g.connect(a.destination); g.gain.setValueAtTime(0.2, a.currentTime); g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime+0.5); o.start(); o.stop(a.currentTime+0.5); }catch(e){}
}

let busy = false;
async function resolveOpen(){
  if(busy) return; busy = true;
  try{
    const now = Math.floor(Date.now()/1000);
    for(const t of journal.filter(t => !t.result)){
      if(now - t.t0 > MAX_AGE){ t.result = 'expired'; t.t1 = now; continue; }
      const n = Math.min(1500, Math.ceil((now - t.t0)/60) + 5);
      let c; try{ const r = await fetch(`${BACK}/api/candles?asset=${t.asset}&tf=M1&count=${n}`); c = await r.json(); }catch(e){ continue; }
      if(!Array.isArray(c) || !c.length) continue;
      const s = settleTrade(t, c);
      if(s){
        Object.assign(t, s);
        toast(`<b style="color:${s.result==='win'?'#29D398':'#FF5C72'}">${s.result==='win' ? 'WIN' : 'LOSS'}</b> · ${t.asset} ${t.side} (${t.src}) · ${s.result==='win' ? '+'+s.r.toFixed(2) : '-1'}R`, s.result==='win' ? '#29D398' : '#FF5C72');
      }
    }
    save(journal); render();
  } finally { busy = false; }
}

async function pollEngine(){
  for(const a of ASSETS){
    if(openCount(a.id, 'S/R')) continue;
    try{
      const d = await (await fetch(`${BACK}/api/signal?asset=${a.id}`)).json();
      if((d.state==='buy' || d.state==='sell') && d.sl && d.tp){
        api.record({ src:'S/R', asset:a.id, tf:'M1', side:d.state.toUpperCase(), entry: d.entry || d.price_exness || d.price, sl:+d.sl, tp:+d.tp });
      }
    }catch(e){}
  }
}

const fmtT = s => { const d = new Date(s*1000); return d.toLocaleDateString('fr-FR',{day:'2-digit',month:'2-digit'}) + ' ' + d.toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'}); };
const fp = p => Math.abs(p) >= 100 ? (+p).toFixed(2) : (+p).toFixed(4);
let filter = 'ALL';

function render(){
  const el = document.getElementById('pfxStats'); if(!el || el.style.display === 'none') return;
  const j = journal.filter(t => filter==='ALL' || t.src===filter);
  const s = stats(j);
  const byAsset = {};
  j.forEach(t => { if(t.result==='win'||t.result==='loss'){ const o = byAsset[t.asset] = byAsset[t.asset] || {w:0,l:0,r:0}; t.result==='win' ? o.w++ : o.l++; o.r += t.r; } });
  const col = v => v >= 0 ? '#29D398' : '#FF5C72';
  let h = `<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">` +
    ['ALL','FIB','S/R'].map(f => `<button data-f="${f}" class="${filter===f?'on':''}">${f==='ALL'?'Tous':f==='FIB'?'Signal Fib':'Support/Résistance'}</button>`).join('') +
    `<button data-act="check">Actualiser</button><button data-act="clear">Effacer le journal</button></div>`;
  h += `<div style="display:flex;gap:22px;flex-wrap:wrap;margin-bottom:12px">
    <div><div class="k">Signaux</div><b>${s.total}</b></div>
    <div><div class="k">WIN</div><b style="color:#29D398">${s.wins}</b></div>
    <div><div class="k">LOSS</div><b style="color:#FF5C72">${s.losses}</b></div>
    <div><div class="k">En cours</div><b>${s.open}</b></div>
    <div><div class="k">Taux de réussite</div><b>${s.closed ? s.winRate.toFixed(1)+'%' : '-'}</b></div>
    <div><div class="k">Total</div><b style="color:${col(s.sumR)}">${s.sumR>=0?'+':''}${s.sumR.toFixed(2)}R</b></div>
    <div><div class="k">Moyenne</div><b style="color:${col(s.avgR)}">${s.closed ? (s.avgR>=0?'+':'')+s.avgR.toFixed(2)+'R' : '-'}</b></div></div>`;
  const rows = Object.keys(byAsset).sort();
  if(rows.length){
    h += `<table><tr><th>Actif</th><th>WIN</th><th>LOSS</th><th>Réussite</th><th>Total R</th></tr>` + rows.map(k => { const o = byAsset[k];
      return `<tr><td>${k}</td><td>${o.w}</td><td>${o.l}</td><td>${(o.w/(o.w+o.l)*100).toFixed(0)}%</td><td style="color:${col(o.r)}">${o.r>=0?'+':''}${o.r.toFixed(2)}R</td></tr>`; }).join('') + `</table><div style="height:10px"></div>`;
  }
  h += `<table><tr><th>Date</th><th>Actif</th><th>Source</th><th>Sens</th><th>Entrée</th><th>SL</th><th>TP</th><th>Résultat</th></tr>` +
    (j.slice().reverse().slice(0,40).map(t => {
      const res = t.result==='win' ? `<b style="color:#29D398">WIN +${t.r.toFixed(2)}R</b>` : t.result==='loss' ? `<b style="color:#FF5C72">LOSS -1R</b>` : t.result==='expired' ? 'expiré' : 'en cours';
      return `<tr><td>${fmtT(t.t0)}</td><td>${t.asset} ${t.tf}</td><td>${t.src}</td><td>${t.side}</td><td>${fp(t.entry)}</td><td>${fp(t.sl)}</td><td>${fp(t.tp)}</td><td>${res}</td></tr>`; }).join('') || `<tr><td colspan="8" style="color:#7C8394">Aucun signal enregistré pour l'instant.</td></tr>`) + `</table>`;
  el.innerHTML = h;
  el.querySelectorAll('button[data-f]').forEach(b => b.addEventListener('click', () => { filter = b.dataset.f; render(); }));
  el.querySelector('button[data-act="check"]').addEventListener('click', () => { resolveOpen(); pollEngine(); });
  el.querySelector('button[data-act="clear"]').addEventListener('click', () => { if(confirm('Effacer tout le journal ?')){ journal = []; save(journal); render(); } });
}

function init(){
  const bar = document.getElementById('pfxBar'); if(!bar) return;
  const st = document.createElement('style');
  st.textContent = `#pfxStats{display:none;width:100%;background:var(--surface,#12161F);border:0.5px solid var(--border,#232838);border-radius:12px;padding:14px;overflow-x:auto;font:12px 'JetBrains Mono',monospace;color:#F0F2F6}
  #pfxStats .k{color:#7C8394;font-size:11px;margin-bottom:2px} #pfxStats b{font-size:16px}
  #pfxStats table{width:100%;border-collapse:collapse} #pfxStats th{color:#7C8394;text-align:left;font-weight:500;padding:4px 8px} #pfxStats td{padding:6px 8px;border-top:0.5px solid #232838}
  #pfxStats button{background:#12161F;border:0.5px solid #232838;color:#7C8394;font:700 11px 'JetBrains Mono',monospace;padding:6px 10px;border-radius:8px;cursor:pointer} #pfxStats button.on{color:#F0F2F6;border-color:#F5B841}`;
  document.head.appendChild(st);
  const btn = document.createElement('button'); btn.textContent = 'Statistiques';
  const panel = document.createElement('div'); panel.id = 'pfxStats';
  btn.addEventListener('click', () => { const open = panel.style.display === 'none' || !panel.style.display; panel.style.display = open ? 'block' : 'none'; btn.classList.toggle('on', open); if(open){ render(); resolveOpen(); } });
  const scan = bar.querySelector('button.scan'); bar.insertBefore(btn, scan || null);
  bar.appendChild(panel);
  setInterval(resolveOpen, 15000);
  setInterval(pollEngine, 5000);
  setTimeout(resolveOpen, 1500); setTimeout(pollEngine, 2500);
}
init();
})(typeof window !== 'undefined' ? window : globalThis);
