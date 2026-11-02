/* Pocket FX - module Structure (HH/HL/LH/LL, BOS/CHoCH, Fibonacci auto, Scanner)
   Calcule tout à partir des bougies déjà affichées -> aucun décalage d'heure. */
(function(root){
'use strict';

// ---- 1 pip par actif (modifiable). Marge = 2 pips ----
const PIP = { GER40:1, CAC40:1, SPX500:1, NAS100:1, US30:1, XAUUSD:0.1, USOIL:0.01, BTCUSD:1 };
const MARGIN_PIPS = 2;
const SWING_N = { M1:8, M5:5, M15:5, H1:4, H4:3 };
const FIB_RATIOS = [0, 0.5, 0.618, 0.786, 1];

function findSwings(c, N){
  const raw = [];
  for(let i=N; i<c.length-N; i++){
    let isH = true, isL = true;
    for(let j=i-N; j<=i+N; j++){
      if(j===i) continue;
      if(j<i){ if(c[j].high >= c[i].high) isH = false; if(c[j].low <= c[i].low) isL = false; }
      else   { if(c[j].high >  c[i].high) isH = false; if(c[j].low <  c[i].low) isL = false; }
      if(!isH && !isL) break;
    }
    if(isH) raw.push({ idx:i, type:'H', price:c[i].high, time:c[i].time });
    if(isL) raw.push({ idx:i, type:'L', price:c[i].low,  time:c[i].time });
  }
  const zz = [];
  for(const s of raw){
    const last = zz[zz.length-1];
    if(last && last.type === s.type){
      if((s.type==='H' && s.price > last.price) || (s.type==='L' && s.price < last.price)) zz[zz.length-1] = s;
    } else zz.push(s);
  }
  return zz;
}

function analyze(c, asset, tf, opts){
  opts = opts || {};
  const N = opts.swingN || SWING_N[tf] || 5;
  const m = MARGIN_PIPS * (PIP[asset] || 1);
  const out = { asset, tf, margin:m, swings:[], events:[], trend:null, fib:null, last:null };
  if(!c || c.length < N*2 + 5) return out;

  const swings = findSwings(c, N);
  let pH = null, pL = null;
  for(const s of swings){
    if(s.type==='H'){ s.label = pH===null ? null : (s.price > pH ? 'HH' : 'LH'); pH = s.price; s.adj = s.price + m; }
    else            { s.label = pL===null ? null : (s.price > pL ? 'HL' : 'LL'); pL = s.price; s.adj = s.price - m; }
    s.confirmIdx = s.idx + N;
  }
  out.swings = swings;

  const broken = new Set();
  const seen = [];
  let trend = null, lastLabH = null, lastLabL = null, lastEventIdx = -1, runStart = -1, si = 0;
  const events = [];
  for(let i=0; i<c.length; i++){
    while(si < swings.length && swings[si].confirmIdx <= i){
      const s = swings[si++]; seen.push(s);
      if(s.label){
        if(s.type==='H') lastLabH = s.label; else lastLabL = s.label;
        if(s.idx > lastEventIdx){
          if(lastLabH==='HH' && lastLabL==='HL' && trend!=='up'){ trend='up'; runStart = Math.max(runStart, lastEventIdx); }
          else if(lastLabH==='LH' && lastLabL==='LL' && trend!=='down'){ trend='down'; runStart = Math.max(runStart, lastEventIdx); }
        }
      }
    }
    if(!trend) continue;
    const price = c[i].close;
    let hi = null, lo = null;
    for(let k=seen.length-1; k>=0 && (!hi || !lo); k--){
      const s = seen[k]; if(broken.has(s)) continue;
      if(s.type==='H' && !hi) hi = s; if(s.type==='L' && !lo) lo = s;
    }
    const sweep = (type, test) => { for(const s of seen) if(s.type===type && test(s)) broken.add(s); };
    if(trend==='up'){
      if(hi && price > hi.adj){ sweep('H', s => s.adj < price); events.push({ kind:'BOS', dir:'up', idx:i, time:c[i].time, level:hi.adj }); lastEventIdx = i; }
      else if(lo && price < lo.adj){ sweep('L', s => s.adj > price); events.push({ kind:'CHoCH', dir:'down', idx:i, time:c[i].time, level:lo.adj }); trend='down'; lastEventIdx = i; runStart = i; lastLabH = lastLabL = null; }
    } else {
      if(lo && price < lo.adj){ sweep('L', s => s.adj > price); events.push({ kind:'BOS', dir:'down', idx:i, time:c[i].time, level:lo.adj }); lastEventIdx = i; }
      else if(hi && price > hi.adj){ sweep('H', s => s.adj < price); events.push({ kind:'CHoCH', dir:'up', idx:i, time:c[i].time, level:hi.adj }); trend='up'; lastEventIdx = i; runStart = i; lastLabH = lastLabL = null; }
    }
  }
  out.trend = trend; out.events = events;
  const lastC = c[c.length-1];
  out.last = { price:lastC.close, idx:c.length-1, time:lastC.time };

  // Fibonacci : baissier = 1er LH (100%) -> 1er LL (0%) ; haussier = 1er HL (100%) -> 1er HH (0%)
  if(trend){
    const run = swings.filter(s => s.idx > runStart && s.confirmIdx <= c.length-1);
    const mode = opts.fibMode || 'first';
    let a = null, b = null;
    const wantA = trend==='down' ? 'LH' : 'HL';
    const wantB = trend==='down' ? 'LL' : 'HH';
    const pairs = [];
    for(let k=0;k<run.length;k++){
      if(run[k].label===wantA){
        for(let j=k+1;j<run.length;j++){ if(run[j].label===wantB){ pairs.push([run[k], run[j]]); break; } }
      }
    }
    if(pairs.length){ const p = mode==='last' ? pairs[pairs.length-1] : pairs[0]; a = p[0]; b = p[1]; }
    if(a && b){
      const p100 = a.adj, p0 = b.adj;
      const levels = FIB_RATIOS.map(r => ({ ratio:r, price: p0 + r*(p100 - p0) }));
      const zLo = Math.min(levels[1].price, levels[3].price), zHi = Math.max(levels[1].price, levels[3].price);
      out.fib = { dir:trend, a, b, p100, p0, levels, zone:[zLo, zHi], inZone: lastC.close >= zLo && lastC.close <= zHi,
                  retrace: (lastC.close - p0) / (p100 - p0) };
    } else out.fib = { dir:trend, waiting: trend==='down' ? 'en attente du 1er LH puis du 1er LL' : 'en attente du 1er HL puis du 1er HH' };
  }
  return out;
}

const api = { PIP, MARGIN_PIPS, SWING_N, FIB_RATIOS, findSwings, analyze };
if(typeof module !== 'undefined' && module.exports){ module.exports = api; }
root.PFX = api;
if(typeof document === 'undefined') return;

/* ============================ INTERFACE ============================ */
const BACKEND_URL = (typeof BACKEND !== 'undefined') ? BACKEND : 'http://localhost:8000';
const shift = () => (typeof timeShift !== 'undefined' ? timeShift : 0);
const st = { fib:false, HH:false, HL:false, LH:false, LL:false, EV:false, fibMode:'first' };
const store = {};
const pending = {};
let sigMarkers = [], fibLines = [], origSetMarkers = null, lastKey = '';

const _fetch = root.fetch.bind(root);
root.fetch = function(url, o){
  const p = _fetch(url, o);
  try{
    const u = String(url);
    if(u.indexOf('/api/candles') >= 0){
      const q = new URL(u, location.href).searchParams;
      p.then(r => r.clone().json()).then(d => {
        if(Array.isArray(d) && d.length){ store[q.get('asset')+'|'+q.get('tf')] = d; setTimeout(render, 150); }
      }).catch(()=>{});
    }
  }catch(e){}
  return p;
};

function hookMarkers(){
  if(typeof candleSeries === 'undefined' || !candleSeries || origSetMarkers) return;
  origSetMarkers = candleSeries.setMarkers.bind(candleSeries);
  candleSeries.setMarkers = function(m){ sigMarkers = m || []; pushMarkers(); };
}
let structMarkers = [];
function pushMarkers(){
  const all = sigMarkers.concat(structMarkers).sort((x,y)=> x.time - y.time);
  try{ origSetMarkers(all); }catch(e){}
}

function current(){
  const key = currentAsset.id + '|' + currentTf;
  const c = store[key];
  if(!c && !pending[key]){
    pending[key] = true;
    _fetch(`${BACKEND_URL}/api/candles?asset=${currentAsset.id}&tf=${currentTf}&count=${typeof candleCount !== 'undefined' ? candleCount : 1500}`)
      .then(r => r.json()).then(d => { if(Array.isArray(d) && d.length){ store[key] = d; render(); } })
      .catch(()=>{}).finally(()=>{ setTimeout(()=>{ delete pending[key]; }, 3000); });
  }
  return c ? analyze(c, currentAsset.id, currentTf, { fibMode: st.fibMode }) : null;
}

function render(){
  hookMarkers();
  const r = current();
  if(!r){ return; }
  const ms = [];
  r.swings.forEach(s => {
    if(!s.label || !st[s.label]) return;
    const hi = s.type==='H';
    ms.push({ time: s.time + shift(), position: hi ? 'aboveBar' : 'belowBar',
              color: hi ? '#FF5C72' : '#29D398', shape: 'circle', text: s.label });
  });
  if(st.EV) r.events.slice(-12).forEach(e => {
    ms.push({ time: e.time + shift(), position: e.dir==='up' ? 'belowBar' : 'aboveBar',
              color: e.kind==='CHoCH' ? '#F5B841' : '#7AA2FF', shape: e.dir==='up' ? 'arrowUp' : 'arrowDown',
              text: e.kind + (e.dir==='up' ? '↑' : '↓') });
  });
  structMarkers = ms; pushMarkers();

  fibLines.forEach(l => { try{ candleSeries.removePriceLine(l); }catch(e){} }); fibLines = [];
  const info = document.getElementById('pfxInfo');
  const f = r.fib;
  if(st.fib && f && f.levels){
    f.levels.forEach(l => {
      const key = l.ratio===0.5 || l.ratio===0.618 || l.ratio===0.786;
      fibLines.push(candleSeries.createPriceLine({
        price:l.price, color: key ? '#F5B841' : '#A78BFA', lineWidth: key ? 2 : 1,
        lineStyle: LightweightCharts.LineStyle.Dotted, axisLabelVisible:true,
        title: 'Fib ' + (l.ratio*100).toFixed(l.ratio===0.618||l.ratio===0.786 ? 1 : 0) + '%' }));
    });
  }
  if(info){
    const t = r.trend ? (r.trend==='up' ? '📈 haussière' : '📉 baissière') : 'indéterminée';
    const ev = r.events[r.events.length-1];
    let txt = `Structure ${currentAsset.id} ${currentTf} : ${t}`;
    if(ev) txt += ` · dernier : ${ev.kind} ${ev.dir==='up'?'↑':'↓'} (${r.last.idx - ev.idx} bougies)`;
    if(st.fib){
      if(f && f.levels) txt += ` · Fib ${f.dir==='down'?'LH→LL':'HL→HH'} · ${(f.retrace*100).toFixed(0)}% ${f.inZone ? '🎯 dans la zone 50–78.6%' : ''}`;
      else if(f && f.waiting) txt += ' · Fib : ' + f.waiting;
    }
    info.textContent = txt;
  }
}

function css(){
  const s = document.createElement('style');
  s.textContent = `
  #pfxBar{display:flex; flex-wrap:wrap; gap:6px; align-items:center}
  #pfxBar button{background:var(--surface,#12161F); border:0.5px solid var(--border,#232838); color:var(--text-muted,#7C8394); font:700 12px 'JetBrains Mono',monospace; padding:7px 11px; border-radius:8px; cursor:pointer}
  #pfxBar button.on{background:var(--surface-2,#181D28); color:var(--text,#F0F2F6); border-color:var(--gold,#F5B841)}
  #pfxBar button.scan{border-color:#7AA2FF; color:#7AA2FF}
  #pfxInfo{font:11px 'JetBrains Mono',monospace; color:var(--text-muted,#7C8394); width:100%}
  #pfxPanel{display:none; background:var(--surface,#12161F); border:0.5px solid var(--border,#232838); border-radius:12px; padding:12px 14px; overflow-x:auto}
  #pfxPanel table{width:100%; border-collapse:collapse; font:12px 'JetBrains Mono',monospace}
  #pfxPanel th{color:var(--text-muted,#7C8394); text-align:left; font-weight:500; padding:4px 8px}
  #pfxPanel td{padding:7px 8px; border-top:0.5px solid var(--border,#232838); color:var(--text,#F0F2F6)}
  #pfxPanel tr.row{cursor:pointer} #pfxPanel tr.row:hover td{background:var(--surface-2,#181D28)}
  .pfx-new{color:#F5B841; font-weight:700}`;
  document.head.appendChild(s);
}

function addButtons(){
  const bar = document.createElement('div'); bar.id = 'pfxBar';
  const def = [['fib','Fibonacci'],['HH','HH'],['HL','HL'],['LH','LH'],['LL','LL'],['EV','BOS/CHoCH']];
  def.forEach(([k,label]) => {
    const b = document.createElement('button'); b.textContent = label; b.dataset.k = k;
    b.addEventListener('click', () => { st[k] = !st[k]; b.classList.toggle('on', st[k]); render(); });
    bar.appendChild(b);
  });
  const mode = document.createElement('button'); mode.textContent = 'Fib : 1er'; mode.title = '1er = premier LH→LL / HL→HH du mouvement ; dernier = le plus récent';
  mode.addEventListener('click', () => { st.fibMode = st.fibMode==='first' ? 'last' : 'first'; mode.textContent = 'Fib : ' + (st.fibMode==='first' ? '1er' : 'dernier'); render(); });
  bar.appendChild(mode);
  const all = document.createElement('button'); all.textContent = 'Tout';
  all.addEventListener('click', () => {
    const on = !(st.HH && st.HL && st.LH && st.LL);
    ['HH','HL','LH','LL'].forEach(k => st[k] = on);
    bar.querySelectorAll('button[data-k]').forEach(b => { if(['HH','HL','LH','LL'].includes(b.dataset.k)) b.classList.toggle('on', on); });
    render();
  });
  bar.appendChild(all);
  const scan = document.createElement('button'); scan.textContent = '🔎 Scanner'; scan.className = 'scan';
  scan.addEventListener('click', runScan); bar.appendChild(scan);
  const info = document.createElement('div'); info.id = 'pfxInfo'; bar.appendChild(info);
  const panel = document.createElement('div'); panel.id = 'pfxPanel';
  const wrap = document.getElementById('chart-wrap');
  wrap.parentNode.insertBefore(bar, wrap);
  wrap.parentNode.insertBefore(panel, wrap);
}

function addTimeframes(){
  const box = document.getElementById('tfToggle'); if(!box) return;
  const mk = (tf, count, before) => {
    if(box.querySelector(`[data-tf="${tf}"]`)) return;
    const b = document.createElement('button'); b.dataset.tf = tf; b.dataset.count = count; b.textContent = tf;
    const ref = box.querySelector(`[data-tf="${before}"]`);
    if(ref) box.insertBefore(b, ref); else box.appendChild(b);
  };
  mk('M15', 6000, 'H1'); mk('H4', 400, null);
}

async function runScan(){
  const panel = document.getElementById('pfxPanel');
  panel.style.display = 'block'; panel.scrollIntoView({behavior:'smooth', block:'nearest'});
  panel.innerHTML = `<div style="color:var(--text-muted)">Scan en cours (${currentTf})…</div>`;
  const rows = [];
  for(const a of ASSETS){
    try{
      const res = await _fetch(`${BACKEND_URL}/api/candles?asset=${a.id}&tf=${currentTf}&count=1500`);
      const c = await res.json();
      if(!Array.isArray(c) || !c.length){ rows.push({ id:a.id, err:'pas de données' }); continue; }
      rows.push({ id:a.id, r: analyze(c, a.id, currentTf, { fibMode: st.fibMode }) });
    }catch(e){ rows.push({ id:a.id, err:'backend hors ligne' }); }
  }
  const age = r => { const e = r.events[r.events.length-1]; return e ? r.last.idx - e.idx : 1e9; };
  rows.sort((x,y) => (x.r ? age(x.r) : 1e10) - (y.r ? age(y.r) : 1e10));
  let h = `<table><tr><th>Actif</th><th>Tendance</th><th>Dernier événement</th><th>Fibonacci</th></tr>`;
  rows.forEach(x => {
    if(x.err){ h += `<tr><td>${x.id}</td><td colspan="3">${x.err}</td></tr>`; return; }
    const r = x.r, e = r.events[r.events.length-1], ag = e ? age(r) : null;
    const tr = r.trend==='up' ? '📈 haussière' : r.trend==='down' ? '📉 baissière' : '—';
    const ev = e ? `${e.kind} ${e.dir==='up'?'↑':'↓'} · il y a ${ag} bougies` + (ag <= 10 ? ' <span class="pfx-new">● NOUVEAU</span>' : '') : '—';
    let fb = '—';
    if(r.fib && r.fib.levels) fb = `${(r.fib.retrace*100).toFixed(0)}% ` + (r.fib.inZone ? '<span class="pfx-new">🎯 zone 50–78.6%</span>' : '');
    else if(r.fib && r.fib.waiting) fb = r.fib.waiting;
    h += `<tr class="row" data-id="${x.id}"><td><b>${x.id}</b></td><td>${tr}</td><td>${ev}</td><td>${fb}</td></tr>`;
  });
  h += `</table><div style="margin-top:8px;font:11px 'JetBrains Mono',monospace;color:var(--text-muted)">Clique une ligne pour ouvrir l'actif.</div>`;
  panel.innerHTML = h;
  panel.querySelectorAll('tr.row').forEach(tr => tr.addEventListener('click', () => {
    const a = ASSETS.find(z => z.id === tr.dataset.id); if(a) selectAsset(a);
  }));
}

css(); addButtons(); addTimeframes(); hookMarkers();
setInterval(() => { const k = currentAsset.id + '|' + currentTf; if(k !== lastKey){ lastKey = k; setTimeout(render, 400); } }, 500);
})(typeof window !== 'undefined' ? window : globalThis);
