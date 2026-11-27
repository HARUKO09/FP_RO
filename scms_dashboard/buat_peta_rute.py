"""Peta rute pengiriman SCMS di atas OpenStreetMap (Leaflet).

Dipakai dari notebook setelah NWCR/LCM/VAM dan MODI dijalankan:

    from buat_peta_rute import buat_peta
    buat_peta(awal, akhir, cost_df, C, blocked, a, b, aktual, 'peta_rute_scms.html')

awal  : {'NWCR': (X0, basic0), ...}
akhir : {'NWCR': (X1, basic1, iterasi, riwayat, D), ...}   (keluaran modi())
Hasilnya satu file .html yang dibuka di browser (butuh internet untuk tile OSM dan Leaflet).
"""
import json
import numpy as np

EPS = 1e-9

# Lokasi representatif (lat, lon). Sumber = kota kantor pusat / pabrik utama kelompok produsen,
# bukan alamat pabrik persis. Tujuan = ibu kota / kota utama negara. Ubah di sini bila perlu.
KOORDINAT_SUMBER = {
    'SCMS RDC': (-26.20, 28.05, 'Johannesburg'),
    'Aurobindo (India)': (17.39, 78.49, 'Hyderabad'),
    'Mylan/Matrix (India)': (17.50, 78.30, 'Hyderabad'),
    'Alere/Inverness (Japan)': (35.68, 139.69, 'Tokyo'),
    'Hetero (India)': (17.30, 78.60, 'Hyderabad'),
    'Cipla (India)': (19.08, 72.88, 'Mumbai'),
    'Strides (India)': (12.97, 77.59, 'Bengaluru'),
    'AbbVie/Abbott (Eropa)': (50.11, 8.68, 'Frankfurt'),
    'Trinity Biotech (Irlandia)': (53.20, -6.10, 'Bray'),
    'KHB (China)': (31.23, 121.47, 'Shanghai'),
    'Standard Diagnostics (Korea)': (37.57, 126.98, 'Seoul'),
    'GSK': (51.49, -0.31, 'Brentford'),
    'Chembio (USA)': (40.82, -73.00, 'Medford, NY'),
    'Micro Labs (India)': (13.10, 77.45, 'Bengaluru'),
    'Emcure (India)': (18.52, 73.86, 'Pune'),
    'MSD': (40.67, -74.29, 'Kenilworth, NJ'),
    'BMS (Eropa)': (48.86, 2.35, 'Paris'),
    'Ranbaxy (India)': (28.46, 77.03, 'Gurugram'),
    'Novartis': (47.56, 7.59, 'Basel'),
    'Orasure (USA)': (40.63, -75.37, 'Bethlehem, PA'),
    'Roche': (47.50, 7.70, 'Basel'),
    'Janssen': (51.32, 4.87, 'Beerse'),
}

KOORDINAT_TUJUAN = {
    'Nigeria': (9.06, 7.49, 'Abuja'), 'Zambia': (-15.39, 28.32, 'Lusaka'),
    'Mozambique': (-25.97, 32.57, 'Maputo'), 'South Africa': (-25.75, 28.19, 'Pretoria'),
    'Zimbabwe': (-17.83, 31.05, 'Harare'), "Côte d'Ivoire": (5.36, -4.01, 'Abidjan'),
    'Tanzania': (-6.79, 39.21, 'Dar es Salaam'), 'Uganda': (0.35, 32.58, 'Kampala'),
    'Rwanda': (-1.95, 30.06, 'Kigali'), 'Vietnam': (21.03, 105.85, 'Hanoi'),
    'Haiti': (18.54, -72.34, 'Port-au-Prince'), 'Ethiopia': (9.03, 38.74, 'Addis Ababa'),
    'Cameroon': (3.85, 11.50, 'Yaoundé'), 'Kenya': (-1.29, 36.82, 'Nairobi'),
    'Ghana': (5.60, -0.19, 'Accra'), 'Namibia': (-22.56, 17.08, 'Windhoek'),
    'Swaziland': (-26.32, 31.14, 'Mbabane'), 'Congo, DRC': (-4.44, 15.27, 'Kinshasa'),
    'Malawi': (-13.96, 33.77, 'Lilongwe'), 'Guyana': (6.80, -58.16, 'Georgetown'),
    'Burundi': (-3.38, 29.36, 'Bujumbura'), 'Botswana': (-24.65, 25.91, 'Gaborone'),
    'Dominican Republic': (18.49, -69.93, 'Santo Domingo'), 'South Sudan': (4.85, 31.58, 'Juba'),
    'Benin': (6.37, 2.39, 'Cotonou'), 'Pakistan': (33.69, 73.05, 'Islamabad'),
    'Guatemala': (14.63, -90.51, 'Guatemala City'), 'Sudan': (15.50, 32.56, 'Khartoum'),
    'Togo': (6.13, 1.22, 'Lomé'), 'Angola': (-8.84, 13.23, 'Luanda'),
    'Libya': (32.89, 13.19, 'Tripoli'), 'Sierra Leone': (8.48, -13.23, 'Freetown'),
    'Lesotho': (-29.31, 27.48, 'Maseru'), 'Mali': (12.64, -8.00, 'Bamako'),
    'Liberia': (6.30, -10.80, 'Monrovia'), 'Guinea': (9.64, -13.58, 'Conakry'),
    'Afghanistan': (34.53, 69.17, 'Kabul'), 'Senegal': (14.72, -17.47, 'Dakar'),
}


def _aliran(X, sumber, tujuan, C, blocked):
    out = []
    for i, j in zip(*np.where(X > EPS)):
        out.append({'s': sumber[i], 't': tujuan[j], 'kg': float(X[i, j]),
                    'c': float(C[i, j]), 'blk': bool(blocked[i, j])})
    out.sort(key=lambda f: -f['kg'])
    return out


def bangun_data(awal, akhir, cost_df, C, blocked, a, b, aktual):
    sumber, tujuan = list(cost_df.index), list(cost_df.columns)
    hilang = [n for n in sumber if n not in KOORDINAT_SUMBER] + \
             [n for n in tujuan if n not in KOORDINAT_TUJUAN]
    if hilang:
        raise KeyError(f'Koordinat belum ada untuk: {hilang}')
    res = {}
    for k in awal:
        X0 = awal[k][0]
        X1, _, it = akhir[k][0], akhir[k][1], akhir[k][2]
        res[k] = {
            'awal': _aliran(X0, sumber, tujuan, C, blocked),
            'modi': _aliran(X1, sumber, tujuan, C, blocked),
            'iter': int(it),
            'cost_awal': float((X0 * C).sum()),
            'cost_awal_valid': float((X0[~blocked] * C[~blocked]).sum()),
            'kg_blk': float(X0[blocked].sum()),
            'cost_modi': float((X1 * C).sum()),
        }
    maks = max(f['kg'] for r in res.values() for tahap in ('awal', 'modi') for f in r[tahap])
    return {
        'meta': {'aktual': float(aktual), 'maxKg': float(maks), 'totalKg': float(np.sum(a))},
        'src': [{'n': n, 'kg': float(v), 'lat': KOORDINAT_SUMBER[n][0], 'lon': KOORDINAT_SUMBER[n][1],
                 'kota': KOORDINAT_SUMBER[n][2]} for n, v in zip(sumber, a)],
        'dst': [{'n': n, 'kg': float(v), 'lat': KOORDINAT_TUJUAN[n][0], 'lon': KOORDINAT_TUJUAN[n][1],
                 'kota': KOORDINAT_TUJUAN[n][2]} for n, v in zip(tujuan, b)],
        'res': res,
    }


def buat_peta(awal, akhir, cost_df, C, blocked, a, b, aktual, path='peta_rute_scms.html'):
    data = bangun_data(awal, akhir, cost_df, C, blocked, a, b, aktual)
    html = TEMPLATE.replace('__DATA__', json.dumps(data, ensure_ascii=False))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return path


TEMPLATE = r'''<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Peta Rute Pengiriman SCMS</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{
  --panel:#ffffff; --ink:#1d2733; --muted:#5d6b7a; --line:#d9dfe6; --accent:#1f5fa8; --accent-ink:#ffffff;
  --warn:#c62828; --warn-bg:#fdecea; --ok:#1b7f4b; --chip:#eef2f6; --shadow:0 2px 14px rgba(20,35,55,.22);
}
@media (prefers-color-scheme:dark){:root{
  --panel:#18202a; --ink:#e6ebf1; --muted:#9aa8b8; --line:#2c3846; --accent:#6aa9ee; --accent-ink:#0d1722;
  --warn:#ff8a80; --warn-bg:#3a1f1f; --ok:#6fd49e; --chip:#243040; --shadow:0 2px 14px rgba(0,0,0,.5);}}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:var(--panel)}
#map{position:absolute;inset:0}
#panel{position:absolute;z-index:1000;top:12px;left:12px;width:340px;max-width:calc(100% - 24px);max-height:calc(100% - 24px);
  display:flex;flex-direction:column;background:var(--panel);border-radius:10px;box-shadow:var(--shadow);overflow:hidden}
#panel header{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px 14px 8px}
#panel h1{font-size:15px;margin:0;line-height:1.25}
#panel h1 small{display:block;font-weight:400;color:var(--muted);font-size:12px;margin-top:2px}
#toggle{border:1px solid var(--line);background:var(--chip);color:var(--ink);border-radius:6px;padding:4px 9px;cursor:pointer;font:inherit;font-size:12px}
#body{overflow-y:auto;padding:0 14px 14px;min-height:0}
#panel.closed #body{display:none}
.lbl{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:12px 0 5px}
.seg{display:flex;border:1px solid var(--line);border-radius:7px;overflow:hidden}
.seg button{flex:1;border:0;background:transparent;color:var(--ink);padding:7px 4px;cursor:pointer;font:inherit;font-weight:600}
.seg button+button{border-left:1px solid var(--line)}
.seg button[aria-pressed=true]{background:var(--accent);color:var(--accent-ink)}
button:focus-visible,.row:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.stats{display:grid;grid-template-columns:1fr auto;gap:3px 12px;font-variant-numeric:tabular-nums}
.stats dt{color:var(--muted)} .stats dd{margin:0;text-align:right;font-weight:600}
.warn{background:var(--warn-bg);color:var(--warn);border-radius:7px;padding:7px 9px;margin-top:8px;font-size:12.5px}
.ok{color:var(--ok)}
.bar{height:9px;border-radius:5px;background:linear-gradient(90deg,#7ad151,#22a884,#2a788e,#414487,#440154)}
.scale{display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-top:3px;font-variant-numeric:tabular-nums}
.keys{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--muted);margin-top:8px}
.keys i{display:inline-block;vertical-align:middle;margin-right:5px}
.k-line{width:22px;border-top:3px solid var(--accent)} .k-blk{width:22px;border-top:3px dashed #d32f2f}
.k-src{width:10px;height:10px;background:#e8731a;border:1px solid #fff} .k-dst{width:10px;height:10px;border-radius:50%;background:#2a6f97;border:1px solid #fff}
.opts{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:13px}
.opts label{display:flex;align-items:center;gap:6px;cursor:pointer}
#focusbar{display:none;align-items:center;justify-content:space-between;gap:8px;background:var(--chip);border-radius:7px;padding:6px 9px;margin-top:10px;font-size:12.5px}
#focusbar button{border:0;background:transparent;color:var(--accent);cursor:pointer;font:inherit;font-weight:600}
.list{border:1px solid var(--line);border-radius:7px;max-height:210px;overflow-y:auto}
.row{display:grid;grid-template-columns:1fr auto;gap:0 10px;padding:6px 9px;cursor:pointer;border-bottom:1px solid var(--line);font-size:12.5px;font-variant-numeric:tabular-nums}
.row:last-child{border-bottom:0} .row:hover{background:var(--chip)}
.row b{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row span{color:var(--muted);text-align:right}
.row.blk b{color:var(--warn)}
.row small{grid-column:1/-1;color:var(--muted);font-size:11.5px}
.note{font-size:11.5px;color:var(--muted);margin-top:10px}
.leaflet-tooltip{font:12.5px/1.4 system-ui,sans-serif}
.leaflet-tooltip b{font-weight:600}
@keyframes alir{to{stroke-dashoffset:-24}}
.anim{stroke-dasharray:8 6;animation:alir 1.4s linear infinite}
@media (prefers-reduced-motion:reduce){.anim{animation:none}}
@media (max-width:560px){#panel{top:auto;bottom:0;left:0;right:0;width:auto;max-width:none;border-radius:12px 12px 0 0;max-height:62%}}
</style>
</head>
<body>
<div id="map" role="application" aria-label="Peta rute pengiriman SCMS"></div>
<aside id="panel">
  <header>
    <h1>Rute pengiriman SCMS<small>22 sumber, 38 negara tujuan, 19,55 juta kg</small></h1>
    <button id="toggle" aria-expanded="true">Sembunyikan</button>
  </header>
  <div id="body">
    <div class="lbl">Metode solusi awal</div>
    <div class="seg" id="seg-metode" role="group" aria-label="Metode">
      <button data-m="NWCR" aria-pressed="false">NWCR</button>
      <button data-m="LCM" aria-pressed="false">LCM</button>
      <button data-m="VAM" aria-pressed="true">VAM</button>
    </div>
    <div class="lbl">Tahap</div>
    <div class="seg" id="seg-tahap" role="group" aria-label="Tahap">
      <button data-t="awal" aria-pressed="false">Solusi awal</button>
      <button data-t="modi" aria-pressed="true">Setelah MODI</button>
    </div>
    <div class="lbl">Ringkasan</div>
    <dl class="stats" id="stats"></dl>
    <div id="warn"></div>
    <div id="focusbar"><span id="focustxt"></span><button id="focusclear">Tampilkan semua</button></div>
    <div class="lbl">Biaya per kg (USD)</div>
    <div class="bar"></div>
    <div class="scale"><span id="cmin"></span><span id="cmax"></span></div>
    <div class="keys">
      <span><i class="k-line"></i>Rute valid, tebal = volume</span>
      <span><i class="k-blk"></i>Rute terblokir (Big-M)</span>
      <span><i class="k-src"></i>Sumber</span>
      <span><i class="k-dst"></i>Tujuan</span>
    </div>
    <div class="lbl">Tampilan</div>
    <div class="opts">
      <label><input type="checkbox" id="o-anim" checked> Animasi aliran</label>
      <label><input type="checkbox" id="o-label"> Label negara</label>
    </div>
    <div class="lbl">Rute terbesar</div>
    <div class="list" id="list"></div>
    <p class="note">Klik penanda sumber atau tujuan untuk menyorot rutenya. Lokasi sumber adalah kota representatif kelompok produsen, bukan alamat pabrik. Garis mengikuti lintasan lingkaran besar, bukan jalur kapal atau pesawat sebenarnya.</p>
  </div>
</aside>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D = __DATA__;
const fmt = (x, d=0) => x.toLocaleString('id-ID', {minimumFractionDigits:d, maximumFractionDigits:d});
const usd = x => 'USD ' + fmt(x);
const STOPS = ['#7ad151','#22a884','#2a788e','#414487','#440154'];
const BLK = '#d32f2f';

const map = L.map('map', {worldCopyJump:true, minZoom:2, zoomSnap:.25}).setView([8, 38], 3);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom:18, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);

const srcBy = Object.fromEntries(D.src.map(s => [s.n, s]));
const dstBy = Object.fromEntries(D.dst.map(s => [s.n, s]));

// skala warna biaya per kg (log), dari semua rute valid
const valid = [];
for (const r of Object.values(D.res)) for (const t of ['awal','modi']) for (const f of r[t]) if (!f.blk) valid.push(f.c);
const cLo = Math.min(...valid), cHi = Math.max(...valid);
document.getElementById('cmin').textContent = fmt(cLo, 2);
document.getElementById('cmax').textContent = fmt(cHi, 2);
function hex(h){return [1,3,5].map(i => parseInt(h.slice(i,i+2),16));}
function warna(c){
  const u = Math.min(1, Math.max(0, (Math.log(c)-Math.log(cLo))/(Math.log(cHi)-Math.log(cLo))));
  const p = u*(STOPS.length-1), i = Math.min(STOPS.length-2, Math.floor(p)), f = p-i;
  const a = hex(STOPS[i]), b = hex(STOPS[i+1]);
  return 'rgb(' + a.map((v,k) => Math.round(v+(b[k]-v)*f)).join(',') + ')';
}
const lebar = kg => 1.6 + 9*Math.sqrt(kg/D.meta.maxKg);

// lintasan lingkaran besar; dipecah di garis tanggal internasional
function busur(p, q, n=72){
  const r = Math.PI/180, f1=p[0]*r, l1=p[1]*r, f2=q[0]*r, l2=q[1]*r;
  const d = 2*Math.asin(Math.sqrt(Math.sin((f2-f1)/2)**2 + Math.cos(f1)*Math.cos(f2)*Math.sin((l2-l1)/2)**2));
  if (d < 1e-3) return [[p, q]];
  const segs = []; let cur = [], prev = null;
  for (let i=0; i<=n; i++){
    const t = i/n, A = Math.sin((1-t)*d)/Math.sin(d), B = Math.sin(t*d)/Math.sin(d);
    const x = A*Math.cos(f1)*Math.cos(l1) + B*Math.cos(f2)*Math.cos(l2);
    const y = A*Math.cos(f1)*Math.sin(l1) + B*Math.cos(f2)*Math.sin(l2);
    const z = A*Math.sin(f1) + B*Math.sin(f2);
    const pt = [Math.atan2(z, Math.hypot(x,y))/r, Math.atan2(y,x)/r];
    if (prev !== null && Math.abs(pt[1]-prev) > 180){ segs.push(cur); cur = []; }
    cur.push(pt); prev = pt[1];
  }
  segs.push(cur);
  return segs;
}

const layerRute = L.layerGroup().addTo(map);
const layerTitik = L.layerGroup().addTo(map);
const layerLabel = L.layerGroup();
let metode = 'VAM', tahap = 'modi', fokus = null, garis = [];

// penanda
const maxSup = Math.max(...D.src.map(s=>s.kg)), maxDem = Math.max(...D.dst.map(d=>d.kg));
for (const s of D.src){
  const z = Math.round(10 + 10*Math.sqrt(s.kg/maxSup));
  const m = L.marker([s.lat, s.lon], {icon:L.divIcon({className:'', iconSize:[z,z], iconAnchor:[z/2,z/2],
    html:`<div style="width:${z}px;height:${z}px;background:#e8731a;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.45)"></div>`}), keyboard:false});
  m.bindTooltip(`<b>${s.n}</b><br>${s.kota}<br>Supply ${fmt(s.kg)} kg`);
  m.on('click', () => setFokus({tipe:'s', n:s.n}));
  m.addTo(layerTitik);
}
for (const d of D.dst){
  const m = L.circleMarker([d.lat, d.lon], {radius:4+9*Math.sqrt(d.kg/maxDem), color:'#fff', weight:1.5, fillColor:'#2a6f97', fillOpacity:.95});
  m.bindTooltip(`<b>${d.n}</b><br>${d.kota}<br>Demand ${fmt(d.kg)} kg`);
  m.on('click', () => setFokus({tipe:'t', n:d.n}));
  m.addTo(layerTitik);
  L.marker([d.lat, d.lon], {interactive:false, icon:L.divIcon({className:'', iconSize:[0,0],
    html:`<div style="transform:translate(8px,-8px);font:600 11px system-ui;color:#12313f;text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 3px #fff;white-space:nowrap">${d.n}</div>`})}).addTo(layerLabel);
}

function aktif(f){ return !fokus || (fokus.tipe==='s' ? f.s===fokus.n : f.t===fokus.n); }

function gambar(){
  layerRute.clearLayers(); garis = [];
  const r = D.res[metode], flows = r[tahap];
  const anim = document.getElementById('o-anim').checked;
  // rute terkecil dulu agar yang besar berada di atas
  [...flows].sort((a,b) => a.kg-b.kg).forEach(f => {
    const s = srcBy[f.s], d = dstBy[f.t], on = aktif(f);
    const pl = L.polyline(busur([s.lat,s.lon],[d.lat,d.lon]), {
      color: f.blk ? BLK : warna(f.c), weight: lebar(f.kg), opacity: on ? (f.blk ? .95 : .82) : .1,
      dashArray: f.blk ? '9 7' : null, lineCap:'round', className: (anim && on && !f.blk) ? 'anim' : ''});
    pl.bindTooltip(`<b>${f.s}</b> → <b>${f.t}</b><br>${fmt(f.kg)} kg<br>USD ${fmt(f.c,2)}/kg${f.blk ? ' <b style="color:#d32f2f">(rute terblokir, biaya Big-M)</b>' : ''}<br>Biaya ${usd(f.kg*f.c)}`, {sticky:true});
    pl.on('mouseover', () => pl.setStyle({weight: lebar(f.kg)+2.5, opacity:1}));
    pl.on('mouseout', () => pl.setStyle({weight: lebar(f.kg), opacity: on ? (f.blk ? .95 : .82) : .1}));
    pl.addTo(layerRute); garis.push({f, pl});
  });
  ringkas(r); daftar(flows);
}

function ringkas(r){
  const st = document.getElementById('stats'), w = document.getElementById('warn');
  const awal = tahap === 'awal';
  const rows = awal ? [
    ['Biaya rute valid', usd(r.cost_awal_valid)],
    ['Biaya + Big-M', usd(r.cost_awal)],
    ['Sel teralokasi', fmt(D.res[metode].awal.length)],
    ['Selisih vs optimal', (r.kg_blk>0 ? 'tidak layak' : '+' + fmt((r.cost_awal_valid/r.cost_modi-1)*100, 2) + '%')],
  ] : [
    ['Biaya optimal', usd(r.cost_modi)],
    ['Iterasi MODI', fmt(r.iter)],
    ['Sel teralokasi', fmt(r.modi.length)],
    ['Hemat vs aktual', fmt((1-r.cost_modi/D.meta.aktual)*100, 2) + '%'],
  ];
  st.innerHTML = rows.map(x => `<dt>${x[0]}</dt><dd>${x[1]}</dd>`).join('');
  if (awal && r.kg_blk > 0){
    const n = r.awal.filter(f=>f.blk).length;
    w.innerHTML = `<div class="warn">${n} rute terblokir terisi, total ${fmt(r.kg_blk)} kg (${fmt(r.kg_blk/D.meta.totalKg*100,1)}% volume). Solusi awal ini belum layak; MODI memindahkan seluruhnya.</div>`;
  } else if (awal){
    w.innerHTML = `<div class="warn ok" style="background:transparent;padding:7px 0 0">Solusi awal sudah layak: tidak ada rute terblokir.</div>`;
  } else {
    w.innerHTML = `<div class="warn ok" style="background:transparent;padding:7px 0 0">Optimal: tidak ada rute terblokir, semua biaya reduksi ≥ 0.</div>`;
  }
}

function daftar(flows){
  const el = document.getElementById('list');
  const rows = flows.filter(aktif).slice(0, 40);
  el.innerHTML = rows.map((f,i) => `<div class="row${f.blk?' blk':''}" tabindex="0" data-i="${flows.indexOf(f)}">
    <b>${f.s} → ${f.t}</b><span>${fmt(f.kg)} kg</span><small>USD ${fmt(f.c,2)}/kg${f.blk?' (terblokir)':''}</small></div>`).join('')
    || '<div class="row"><b>Tidak ada rute</b></div>';
  el.querySelectorAll('.row[data-i]').forEach(row => {
    const go = () => {
      const f = D.res[metode][tahap][+row.dataset.i];
      const g = garis.find(x => x.f === f); if (!g) return;
      map.fitBounds(g.pl.getBounds(), {padding:[60,60], maxZoom:6}); g.pl.openTooltip(g.pl.getBounds().getCenter());
    };
    row.addEventListener('click', go);
    row.addEventListener('keydown', e => { if (e.key==='Enter' || e.key===' '){ e.preventDefault(); go(); } });
  });
}

function setFokus(x){
  fokus = (fokus && x && fokus.tipe===x.tipe && fokus.n===x.n) ? null : x;
  const bar = document.getElementById('focusbar');
  bar.style.display = fokus ? 'flex' : 'none';
  if (fokus) document.getElementById('focustxt').textContent = (fokus.tipe==='s' ? 'Sumber: ' : 'Tujuan: ') + fokus.n;
  gambar();
}

function pasang(id, attr, set){
  document.querySelectorAll('#'+id+' button').forEach(b => b.addEventListener('click', () => {
    set(b.dataset[attr]);
    document.querySelectorAll('#'+id+' button').forEach(x => x.setAttribute('aria-pressed', x===b));
    gambar();
  }));
}
pasang('seg-metode', 'm', v => metode = v);
pasang('seg-tahap', 't', v => tahap = v);
document.getElementById('focusclear').addEventListener('click', () => setFokus(null));
document.getElementById('o-anim').addEventListener('change', gambar);
document.getElementById('o-label').addEventListener('change', e => e.target.checked ? layerLabel.addTo(map) : map.removeLayer(layerLabel));
document.getElementById('toggle').addEventListener('click', e => {
  const p = document.getElementById('panel'), closed = p.classList.toggle('closed');
  e.target.textContent = closed ? 'Tampilkan' : 'Sembunyikan'; e.target.setAttribute('aria-expanded', !closed);
});
if (innerWidth <= 560) document.getElementById('toggle').click();
gambar();
</script>
</body>
</html>
'''
