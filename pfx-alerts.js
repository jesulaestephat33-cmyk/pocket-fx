/* Pocket FX - alertes : son + bandeau quand un actif change de structure ou entre dans la zone Fib 50-78.6% */
(function(){
'use strict';
if(typeof PFX === 'undefined' || typeof document === 'undefined') return;
const URL_BACKEND = (typeof BACKEND !== 'undefined') ? BACKEND : 'http://localhost:8000';
const CHECK_MS = 30000;
let on = false, timer = null, audio = null, titleTimer = null;
const seen = {};

function beep(){
  try{
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    [880, 1175, 880].forEach((f, i) => {
      const o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = f; o.type = 'sine'; o.connect(g); g.connect(audio.destination);
      const t = audio.currentTime + i * 0.18;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.25, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
      o.start(t); o.stop(t + 0.17);
    });
  }catch(e){}
}

function box(){
  let b = document.getElementById('pfxAlerts');
  if(!b){
    b = document.createElement('div'); b.id = 'pfxAlerts';
    b.style.cssText = 'position:fixed;top:14px;right:14px;z-index:9999;display:flex;flex-direction:column;gap:8px;max-width:340px';
    document.body.appendChild(b);
  }
  return b;
}
function notify(id, text){
  beep();
  const d = document.createElement('div');
  d.style.cssText = "background:#181D28;border:1px solid #F5B841;color:#F0F2F6;padding:10px 14px;border-radius:10px;font:12px 'JetBrains Mono',monospace;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.45)";
  d.innerHTML = `<b style="color:#F5B841">${id}</b> · ${text}`;
  d.addEventListener('click', () => { const a = ASSETS.find(z => z.id === id); if(a) selectAsset(a); d.remove(); });
  box().appendChild(d);
  setTimeout(() => d.remove(), 20000);
  const base = document.title; let n = 0;
  clearInterval(titleTimer);
  titleTimer = setInterval(() => { document.title = (n++ % 2) ? base.replace(/^🔔 .*? · /, '') : `🔔 ${id} · ${base.replace(/^🔔 .*? · /, '')}`; if(n > 10){ clearInterval(titleTimer); document.title = base.replace(/^🔔 .*? · /, ''); } }, 800);
}

async function check(){
  const tf = currentTf;
  for(const a of ASSETS){
    try{
      const res = await fetch(`${URL_BACKEND}/api/candles?asset=${a.id}&tf=${tf}&count=1500`);
      const c = await res.json();
      if(!Array.isArray(c) || !c.length) continue;
      const r = PFX.analyze(c, a.id, tf, { fibMode:'first' });
      const key = a.id + '|' + tf;
      const ev = r.events[r.events.length-1];
      const cur = { evTime: ev ? ev.time : null, inZone: !!(r.fib && r.fib.inZone) };
      const prev = seen[key];
      if(prev){
        if(cur.evTime && cur.evTime !== prev.evTime)
          notify(a.id, `${ev.kind} ${ev.dir==='up' ? '↑ haussier' : '↓ baissier'} (${tf})`);
        if(cur.inZone && !prev.inZone)
          notify(a.id, `🎯 entre dans la zone Fib 50–78.6% (${tf})`);
      }
      seen[key] = cur;
    }catch(e){}
  }
}

function toggle(btn){
  on = !on; btn.classList.toggle('on', on);
  btn.textContent = on ? '🔔 Alertes ON' : '🔔 Alertes';
  clearInterval(timer);
  if(on){ beep(); check(); timer = setInterval(check, CHECK_MS); }
}

const bar = document.getElementById('pfxBar');
if(bar){
  const b = document.createElement('button'); b.textContent = '🔔 Alertes';
  b.title = 'Son + bandeau quand un actif change de structure ou entre dans la zone Fib (scan toutes les 30 s, timeframe affiché)';
  b.addEventListener('click', () => toggle(b));
  const scan = bar.querySelector('button.scan');
  bar.insertBefore(b, scan || null);
}
window.PFXA = { check, seen };
})();
