"""Build ONE self-contained PER Model explorer covering all three PER models.

Embeds the AWGN catalog (per_catalog.npz), the raw Channel-D + BF catalog
(per_catalog_chd.npz), and its smoothed variant (per_catalog_chd_smooth.npz)
into a single standalone PER_Model_Combined.html. A top "Channel model" selector
switches between AWGN / Channel D (sim) / Channel D (smoothed); each keeps its own
native dimensions and cascading selectors:

  AWGN       : frameBW, channelBW, antenna, GI                     (+ MCS)
  Channel D  : format, frameBW, channelBW, antenna, Nss, GI, LTF, control  (+ MCS)

Run from repo root (after the per_catalog*.npz builders):
    python PERModel/build_per_model_combined.py
"""
from __future__ import annotations

import json
import os

import numpy as np

HERE = os.path.dirname(__file__)
CAT_AWGN = os.path.join(HERE, "per_catalog.npz")
CAT_CHD = os.path.join(HERE, "per_catalog_chd.npz")
CAT_CHDS = os.path.join(HERE, "per_catalog_chd_smooth.npz")
OUT = os.path.join(HERE, "PER_Model_Combined.html")


def load_catalog(path: str) -> dict:
    d = np.load(path)
    keys = [str(k) for k in d["keys"]]
    cat = {}
    for i, k in enumerate(keys):
        cat[k] = {
            "s": [round(float(v), 2) for v in d[f"x{i}"]],
            "p": [round(float(v), 5) for v in d[f"y{i}"]],
        }
    return cat


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PER Model - combined (AWGN + Channel D)</title>
<style>
  :root{--blue:#0071C5;--dark:#1F2A44;--green:#2E8B57;--orange:#E8820C;
        --red:#C0392B;--light:#EAF3FB;--grey:#6b7280;--card:#fff;--purple:#7C3AED;}
  *{box-sizing:border-box;font-family:"Segoe UI",system-ui,Arial,sans-serif;}
  body{margin:0;background:linear-gradient(160deg,#f4f8fc,#e8eef6);color:var(--dark);}
  header{background:var(--dark);color:#fff;padding:18px 26px;}
  header h1{margin:0;font-size:24px;}
  header p{margin:4px 0 0;color:#b9c6d8;font-size:14px;}
  .wrap{max-width:1080px;margin:0 auto;padding:22px;}
  .card{background:var(--card);border-radius:14px;padding:20px;box-shadow:0 4px 14px rgba(20,40,80,.08);margin-bottom:20px;}
  .card h2{margin:0 0 12px;font-size:17px;color:var(--blue);}
  .tabrow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:3px 0;}
  .tabrow .lbl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.3px;color:var(--grey);width:96px;}
  .tabs{display:inline-flex;background:#eef2f7;border-radius:8px;padding:3px;gap:3px;flex-wrap:wrap;}
  .tab{cursor:pointer;border:none;background:transparent;border-radius:6px;padding:3px 9px;
       font-size:12px;font-weight:700;color:var(--grey);transition:.12s;}
  .tab:hover{color:var(--dark);}
  .tab.active{background:var(--blue);color:#fff;box-shadow:0 2px 6px rgba(0,113,197,.35);}
  .modelrow .lbl{color:var(--dark);}
  .modelrow .tabs{background:#e7eefc;padding:4px;}
  .modelrow .tab{font-size:13px;padding:5px 14px;}
  .modelrow .tab.active{background:var(--purple);box-shadow:0 2px 6px rgba(124,58,237,.35);}
  .note{font-size:13px;color:var(--grey);margin-top:10px;line-height:1.5;}
  table.sens{border-collapse:collapse;width:100%;font-size:12.5px;margin-top:6px;}
  table.sens th,table.sens td{border:1px solid #e2e8f0;padding:4px 7px;text-align:center;}
  table.sens th{background:#f1f5f9;color:var(--dark);}
  .val{float:right;color:var(--blue);font-weight:700;}
  label{font-weight:600;font-size:14px;display:block;margin:6px 0 6px;}
  input[type=range]{width:100%;height:6px;border-radius:5px;accent-color:var(--blue);}
  .toggle{display:inline-flex;gap:6px;align-items:center;font-size:13px;font-weight:600;color:var(--grey);cursor:pointer;}
  .badge{display:inline-block;color:#fff;font-size:11px;font-weight:700;border-radius:6px;padding:2px 8px;margin-left:8px;vertical-align:middle;}
  footer{text-align:center;color:var(--grey);font-size:12px;padding:16px;}
</style>
</head>
<body>
<header>
  <h1>&#128200; PER Model <span class="badge" id="modelBadge" style="background:var(--purple)">combined</span></h1>
  <p id="subhead">Measured PER-vs-SNR curves. Pick a <b>channel model</b>, then any permutation. Fully self-contained &mdash; no external files.</p>
</header>

<div class="wrap">
  <div class="card" id="selCard"></div>

  <div class="card">
    <div class="tabrow" style="margin-bottom:2px;">
      <label style="margin:0;">SNR marker <span class="val" id="snrV">25 dB</span></label>
    </div>
    <input type="range" id="snr" min="-5" max="45" value="25">
    <label class="toggle" style="margin-top:10px;"><input type="checkbox" id="logY" checked> Logarithmic PER axis</label>
    <button id="dlBtn" style="margin-top:12px;cursor:pointer;border:none;border-radius:8px;padding:9px 14px;font-size:13px;font-weight:700;color:#fff;background:linear-gradient(90deg,var(--green),var(--blue));">&#11015; Download sensitivity CSV (current model)</button>
  </div>

  <div class="card">
    <h2 id="chartTitle">PER vs SNR &mdash; all MCS</h2>
    <div class="note" id="mcsLegend" style="margin-top:0;"></div>
    <canvas id="perChart" width="1020" height="300" style="width:100%;"></canvas>
    <div class="note" id="perNote"></div>
  </div>

  <div class="card">
    <h2>Sensitivity &mdash; SNR needed per MCS (10% PER)</h2>
    <div id="sensTable"></div>
  </div>
</div>

<footer id="foot"></footer>

<script>
const MODELS = __MODELS__;
const MODEL_ORDER = ["awgn", "chD", "chDs"];
const FLOOR = 1e-3;
const LABELS = {format:"Format",fbw:"Frame BW",chbw:"Channel BW",ant:"Antenna",
                nss:"Streams",gi:"GI",ltf:"LTF",control:"BF control"};
const UNIT = {fbw:" MHz",chbw:" MHz",gi:" \\u00b5s"};
const CTRL_ORDER = ["LOW1","LOW2","LOW4","LOW6","LOW8","HIGH1","HIGH2","HIGH4","HIGH8"];
const LOCKED = new Set(["ltf"]);                // LTF=2 is buggy; row shown but grayed/non-selectable

let modelKey = "awgn";
let M = null;                 // active model view {cat,dims,split,mcsAll,maxM,xmin,xmax}
let state = {};

function setModel(k){
  modelKey = k;
  const m = MODELS[k];
  const split = Object.keys(m.cat).map(key=>key.split(","));
  const mcsIdx = m.dims.length;
  const mcsAll = [...new Set(split.map(r=>+r[mcsIdx]))].sort((a,b)=>a-b);
  M = {cat:m.cat, dims:m.dims, split, mcsIdx, mcsAll, maxM:Math.max(...mcsAll),
       xmin:m.xmin, xmax:m.xmax, label:m.label, nperms:m.nperms};
  const prev = state || {};                        // carry the selection across models
  state = Object.fromEntries(M.dims.map((d,i)=>[d, prev[d] !== undefined ? prev[d] : split[0][i]]));
  reconcile();
  document.getElementById('modelBadge').textContent = m.label;
  document.getElementById('foot').textContent = m.foot;
}

function cmp(dim){ return (a,b)=>{
  if(dim==="control") return CTRL_ORDER.indexOf(a)-CTRL_ORDER.indexOf(b);
  const na=parseFloat(a), nb=parseFloat(b);
  if(!isNaN(na)&&!isNaN(nb)) return na-nb;
  return a<b?-1:a>b?1:0; }; }

function valsFor(idx){
  const set=new Set();
  outer: for(const row of M.split){
    for(let i=0;i<idx;i++){ if(row[i]!==String(state[M.dims[i]])) continue outer; }
    set.add(row[idx]);
  }
  return [...set].sort(cmp(M.dims[idx]));
}
function reconcile(){
  for(let i=0;i<M.dims.length;i++){ const vals=valsFor(i).map(String);
    if(!vals.includes(String(state[M.dims[i]]))) state[M.dims[i]]=vals[0]; }
}
function pref(){ return M.dims.map(d=>state[d]).join(","); }
function keyOf(m){ return pref()+","+m; }
function fmtVal(dim,v){ return v+(UNIT[dim]||""); }

function perLookup(m,snr){
  const e = M.cat[keyOf(m)];
  if(!e) return null;
  const s=e.s, p=e.p, n=s.length;
  if(snr < s[0])   return 1;
  if(snr > s[n-1]) return 0;
  let v = p[n-1];
  for(let i=1;i<n;i++){ if(snr<=s[i]){ const t=(snr-s[i-1])/(s[i]-s[i-1]); v = p[i-1]+t*(p[i]-p[i-1]); break; } }
  return v < FLOOR ? 0 : v;
}
function snrAtPer(m,target){
  const e=M.cat[keyOf(m)]; if(!e) return null;
  const s=e.s,p=e.p;
  for(let i=1;i<s.length;i++){ if((p[i-1]-target)*(p[i]-target)<=0 && p[i-1]!==p[i]){
    const t=(target-p[i-1])/(p[i]-p[i-1]); return +(s[i-1]+t*(s[i]-s[i-1])).toFixed(1); } }
  return null;
}
const mcsColor=m=>'hsl('+Math.round(210*(1-m/M.maxM))+',75%,45%)';

function subtitle(){
  return M.dims.map(d=>{
    if(d==="fbw"||d==="chbw") return state[d]+' MHz';
    if(d==="gi") return state[d]+'\\u00b5s GI';
    if(d==="nss") return state[d]+'ss';
    if(d==="ltf") return 'LTF '+state[d];
    return state[d];
  }).join(' \\u00b7 ');
}

function draw(){
  const cur=+document.getElementById('snr').value;
  const logY=document.getElementById('logY').checked;
  document.getElementById('chartTitle').textContent='PER vs SNR \\u2014 all MCS  \\u00b7  '+subtitle();
  const c=document.getElementById('perChart'); const ctx=c.getContext('2d');
  const W=c.width,H=c.height; ctx.clearRect(0,0,W,H); ctx.font='12px Segoe UI';
  const padL=54,padR=16,padT=34,padB=34, plotW=W-padL-padR, plotH=H-padT-padB;
  const list=M.mcsAll.filter(m=>M.cat[keyOf(m)]);
  if(!list.length){ ctx.fillStyle='#94a3b8'; ctx.textAlign='center'; ctx.fillText('No measured curves for this permutation.',W/2,H/2);
      document.getElementById('perNote').textContent=''; document.getElementById('sensTable').innerHTML=''; return; }
  const xmin=M.xmin, xmax=M.xmax;
  const xTo=v=>padL+(v-xmin)/(xmax-xmin)*plotW;
  const L1=Math.log10(1), LF=Math.log10(FLOOR);
  const yTo=v=>{ if(logY){ const cl=Math.max(v,FLOOR); return padT+plotH*(Math.log10(cl)-L1)/(LF-L1); }
                 return padT+plotH-v*plotH; };
  const yticks = logY ? [1,0.1,0.01,0.001] : [0,0.2,0.4,0.6,0.8,1.0];
  for(const v of yticks){ const y=yTo(v);
    ctx.strokeStyle='#e6ebf2'; ctx.beginPath(); ctx.moveTo(padL,y); ctx.lineTo(W-padR,y); ctx.stroke();
    ctx.fillStyle='#94a3b8'; ctx.textAlign='right'; ctx.fillText((v*100>=1?Math.round(v*100):(v*100).toFixed(v>=0.001?1:2))+'%',padL-6,y+4); }
  ctx.textAlign='center';
  for(let g=Math.ceil(xmin/5)*5; g<=xmax; g+=5){ const x=xTo(g);
    ctx.strokeStyle='#f1f4f8'; ctx.beginPath(); ctx.moveTo(x,padT); ctx.lineTo(x,padT+plotH); ctx.stroke();
    ctx.fillStyle='#94a3b8'; ctx.fillText(g,x,H-16); }
  for(const m of list){
    ctx.strokeStyle=mcsColor(m); ctx.globalAlpha=0.9; ctx.lineWidth=2;
    ctx.beginPath();
    for(let px=0; px<=plotW; px+=2){ const snr=xmin+(px/plotW)*(xmax-xmin);
      const y=yTo(perLookup(m,snr)); px?ctx.lineTo(padL+px,y):ctx.moveTo(padL+px,y); }
    ctx.stroke();
    const xm=snrAtPer(m,0.5);
    if(xm!=null && xm>=xmin && xm<=xmax){ ctx.globalAlpha=1; ctx.textAlign='center'; ctx.font='bold 12px Segoe UI';
      ctx.lineWidth=3; ctx.strokeStyle='#fff'; ctx.strokeText(m, xTo(xm), yTo(0.5)-4);
      ctx.fillStyle=mcsColor(m); ctx.fillText(m, xTo(xm), yTo(0.5)-4); }
  }
  ctx.globalAlpha=1;
  { let lx=padL, ly=4; ctx.textAlign='left'; ctx.fillStyle='#334155'; ctx.font='bold 11px Segoe UI'; ctx.fillText('MCS',lx,ly+12); lx+=32;
    for(const m of list){ ctx.fillStyle=mcsColor(m); ctx.fillRect(lx,ly,16,16); ctx.fillStyle='#fff'; ctx.font='bold 10px Segoe UI'; ctx.textAlign='center'; ctx.fillText(m,lx+8,ly+12); lx += 16 + (m>=10?20:15); } ctx.textAlign='left'; }
  const xc=xTo(cur);
  ctx.strokeStyle='#1F2A44'; ctx.lineWidth=1.6; ctx.setLineDash([5,4]);
  ctx.beginPath(); ctx.moveTo(xc,padT); ctx.lineTo(xc,padT+plotH); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle='#1F2A44'; ctx.textAlign='left'; ctx.font='bold 12px Segoe UI';
  ctx.fillText(cur+' dB', Math.min(xc+6,W-padR-52), padT+12);
  ctx.fillStyle='#475569'; ctx.textAlign='center'; ctx.font='12px Segoe UI';
  ctx.fillText('SNR (dB) \\u2192', padL+plotW/2, H-2);
  ctx.save(); ctx.translate(14,padT+plotH/2); ctx.rotate(-Math.PI/2); ctx.fillText('PER'+(logY?' (log)':''),0,0); ctx.restore();
  document.getElementById('perNote').textContent =
    list.length+' curves \\u2014 one per MCS. The number by each curve = its MCS index. '+
    'Dashed line = SNR marker ('+cur+' dB). '+M.label+' \\u00b7 '+subtitle()+'. PER below 0.1% is treated as 0.';
  document.getElementById('mcsLegend').innerHTML =
    '<b>MCS index</b>: <span style="color:#0071C5">0 = slowest / most robust</span> \\u2192 <span style="color:#C0392B">higher = faster (needs more SNR)</span>. Colour key is on the graph.';
  let html='<table class="sens"><tr><th>MCS</th>'+list.map(m=>'<th style="color:'+mcsColor(m)+'">'+m+'</th>').join('')+'</tr>'+
           '<tr><th>SNR@10% PER (dB)</th>'+list.map(m=>{const v=snrAtPer(m,0.1);return '<td>'+(v!=null?v:'\\u2013')+'</td>';}).join('')+'</tr>'+
           '<tr><th>PER @ '+cur+' dB</th>'+list.map(m=>{const v=perLookup(m,cur);return '<td>'+(v*100).toFixed(v<0.1?1:0)+'%</td>';}).join('')+'</tr></table>';
  document.getElementById('sensTable').innerHTML=html;
}

function buildTabs(){
  const card=document.getElementById('selCard'); card.innerHTML='';
  // channel-model selector
  const mrow=document.createElement('div'); mrow.className='tabrow modelrow';
  const mlbl=document.createElement('span'); mlbl.className='lbl'; mlbl.textContent='Channel model';
  const mbox=document.createElement('div'); mbox.className='tabs';
  for(const k of MODEL_ORDER){ const b=document.createElement('button');
    b.className='tab'+(modelKey===k?' active':''); b.textContent=MODELS[k].label;
    b.onclick=()=>{ setModel(k); buildTabs(); draw(); };
    mbox.appendChild(b); }
  mrow.appendChild(mlbl); mrow.appendChild(mbox); card.appendChild(mrow);
  // dimension selectors for the active model
  M.dims.forEach((dim,idx)=>{
    const row=document.createElement('div'); row.className='tabrow';
    const lbl=document.createElement('span'); lbl.className='lbl'; lbl.textContent=LABELS[dim];
    const box=document.createElement('div'); box.className='tabs';
    for(const v of valsFor(idx)){
      const locked=LOCKED.has(dim);
      const b=document.createElement('button');
      b.className='tab'+(String(state[dim])===String(v)?' active':'')+(locked?' dim':'');
      b.textContent=fmtVal(dim,v);
      if(!locked) b.onclick=()=>{ state[dim]=v; reconcile(); buildTabs(); draw(); };
      box.appendChild(b);
    }
    row.appendChild(lbl); row.appendChild(box); card.appendChild(row);
  });
}
document.getElementById('snr').addEventListener('input',e=>{ document.getElementById('snrV').textContent=e.target.value+' dB'; draw(); });
document.getElementById('logY').addEventListener('change',draw);

function downloadSensitivityCsv(){
  const seen=new Set(); const prefixes=[]; const n=M.dims.length;
  for(const row of M.split){ const pre=row.slice(0,n).join(','); if(!seen.has(pre)){ seen.add(pre); prefixes.push(row.slice(0,n)); } }
  const rows=[M.dims.map(d=>LABELS[d]).concat(M.mcsAll.map(m=>'MCS'+m)).join(',')];
  for(const pre of prefixes){
    const cells=pre.slice();
    for(const m of M.mcsAll){ const e=M.cat[pre.join(',')+','+m];
      let v=null; if(e){ const s=e.s,p=e.p; for(let i=1;i<s.length;i++){ if((p[i-1]-0.1)*(p[i]-0.1)<=0 && p[i-1]!==p[i]){ const t=(0.1-p[i-1])/(p[i]-p[i-1]); v=+(s[i-1]+t*(s[i]-s[i-1])).toFixed(1); break; } } }
      cells.push(v!=null?v:''); }
    rows.push(cells.join(','));
  }
  const blob=new Blob([rows.join('\\n')],{type:'text/csv'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='PER_sensitivity_'+modelKey+'.csv'; a.click(); URL.revokeObjectURL(a.href);
}
document.getElementById('dlBtn').addEventListener('click',downloadSensitivityCsv);

setModel('awgn'); buildTabs(); draw();
</script>
</body>
</html>
"""


def build():
    awgn = load_catalog(CAT_AWGN)
    chd = load_catalog(CAT_CHD)
    chds = load_catalog(CAT_CHDS)
    drop_ltf2 = lambda c: {k: v for k, v in c.items() if k.split(",")[6] != "2"}
    chd = drop_ltf2(chd)                                             # drop buggy LTF=2
    chds = drop_ltf2(chds)
    n_awgn = len({",".join(k.split(",")[:4]) for k in awgn})
    n_chd = len({",".join(k.split(",")[:8]) for k in chd})
    chd_dims = ["format", "fbw", "chbw", "ant", "nss", "gi", "ltf", "control"]
    models = {
        "awgn": {
            "label": "AWGN",
            "dims": ["fbw", "chbw", "ant", "gi"],
            "xmin": -5, "xmax": 45,
            "nperms": n_awgn,
            "foot": (f"AWGN model: measured EHT PER (LDPC, SU, PPM 0, RUindex 1). "
                     f"Source per_catalog.npz. {len(awgn)} curves / {n_awgn} permutations."),
            "cat": awgn,
        },
        "chD": {
            "label": "Channel D (sim)",
            "dims": chd_dims,
            "xmin": -5, "xmax": 45,
            "nperms": n_chd,
            "foot": (f"Channel-D model (raw simulation): measured PER over IEEE channel D "
                     f"with BF (SU, LDPC, PPM 0, RUindex 1). Source per_catalog_chd.npz. "
                     f"{len(chd)} curves / {n_chd} permutations. "
                     f"LTF=2 excluded (known model bug - ignore)."),
            "cat": chd,
        },
        "chDs": {
            "label": "Channel D (smoothed)",
            "dims": chd_dims,
            "xmin": -5, "xmax": 45,
            "nperms": n_chd,
            "foot": (f"Channel-D model (smoothed): the same data as 'Channel D (sim)' with "
                     f"finite-packet Monte-Carlo artifacts (stair-steps, ~10% shelf, tail "
                     f"spikes) removed by landmark-preserving anchored de-shelfing - the "
                     f"onset, 10% and 0.1% points are kept, only the interior is redrawn "
                     f"(isotonic + monotone PCHIP). Source per_catalog_chd_smooth.npz. "
                     f"{len(chds)} curves / {n_chd} permutations. "
                     f"LTF=2 excluded (known model bug - ignore)."),
            "cat": chds,
        },
    }
    data = json.dumps(models, separators=(",", ":"))
    html = HTML.replace("__MODELS__", data)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved {OUT}: AWGN {len(awgn)}/{n_awgn} + Channel-D sim {len(chd)}/{n_chd} + "
          f"Channel-D smoothed {len(chds)}/{n_chd}, {os.path.getsize(OUT)/1024:.0f} KB")


if __name__ == "__main__":
    build()
