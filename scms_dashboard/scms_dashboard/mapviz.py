import html
import math
import numpy as np
import folium
from folium import plugins

TILES = {
    "Gelap (OpenStreetMap + filter)": ("dark", "#0b0e14"),
    "OpenStreetMap standar": (None, "#f2efe9"),
    "Abu-abu terang (OpenStreetMap + filter)": ("gray", "#f5f5f5"),
}

FILTERS = {
    "dark": "invert(1) hue-rotate(180deg) brightness(0.92) contrast(0.88) saturate(0.55)",
    "gray": "grayscale(1) brightness(1.04) contrast(0.92)",
}

STOPS = [(0.0, (0, 229, 255)), (0.35, (118, 255, 3)), (0.6, (255, 234, 0)),
         (0.82, (255, 145, 0)), (1.0, (255, 45, 149))]

SOURCE_PALETTE = ["#00E5FF", "#FF1744", "#76FF03", "#FFEA00", "#FF9100", "#D500F9", "#00E676", "#FF4081",
                  "#18FFFF", "#FFD740", "#69F0AE", "#E040FB", "#FF6E40", "#B2FF59", "#40C4FF", "#FFAB40",
                  "#EEFF41", "#7C4DFF", "#64FFDA", "#F50057", "#C6FF00", "#00B0FF"]

SRC_COLOR = "#2979FF"
DST_COLOR = "#FF1744"


def gradient(t):
    t = min(max(float(t), 0.0), 1.0)
    for (t0, c0), (t1, c1) in zip(STOPS[:-1], STOPS[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return "#%02x%02x%02x" % tuple(int(round(a + (b - a) * u)) for a, b in zip(c0, c1))
    return "#%02x%02x%02x" % STOPS[-1][1]


def arc(p0, p1, n=40, bend=0.18):
    lat0, lon0 = p0; lat1, lon1 = p1
    dlat, dlon = lat1 - lat0, lon1 - lon0
    dist = math.hypot(dlat, dlon)
    if dist < 1e-6:
        return [(lat0, lon0), (lat1, lon1)]
    plat, plon = -dlon, dlat
    if plat < 0 or (plat == 0 and plon < 0):
        plat, plon = -plat, -plon
    norm = math.hypot(plat, plon)
    clat = (lat0 + lat1) / 2 + plat / norm * dist * bend
    clon = (lon0 + lon1) / 2 + plon / norm * dist * bend
    t = np.linspace(0, 1, n)
    lat = (1 - t) ** 2 * lat0 + 2 * (1 - t) * t * clat + t ** 2 * lat1
    lon = (1 - t) ** 2 * lon0 + 2 * (1 - t) * t * clon + t ** 2 * lon1
    return list(zip(lat.tolist(), lon.tolist()))


def fmt_int(x):
    return f"{x:,.0f}"


def build_map(routes, coords, supply, demand, tile_name, color_mode="Biaya per kg (gradasi)",
              animate=False, width_scale=1.0, height=640, source_order=None):
    mode, bg = TILES[tile_name]
    m = folium.Map(location=[15, 20], zoom_start=2, min_zoom=2, tiles="OpenStreetMap", control_scale=True)
    if mode:
        css = f".leaflet-tile-pane{{filter:{FILTERS[mode]};}} .leaflet-container{{background:{bg};}}"
        m.get_root().header.add_child(folium.Element(f"<style>{css}</style>"))
    plugins.Fullscreen().add_to(m)

    valid = routes[~routes["Terblokir"]] if len(routes) else routes
    if len(valid):
        cmin = max(float(valid["Biaya (USD/kg)"].min()), 1e-6)
        cmax = max(float(valid["Biaya (USD/kg)"].max()), cmin * 1.0001)
    else:
        cmin, cmax = 1.0, 10.0
    lmin, lmax = math.log(cmin), math.log(cmax)
    fmax = float(routes["Alokasi (kg)"].max()) if len(routes) else 1.0
    src_list = source_order or list(supply.index)
    src_color = {s: SOURCE_PALETTE[k % len(SOURCE_PALETTE)] for k, s in enumerate(src_list)}

    used_nodes = set()
    layer = folium.FeatureGroup(name="Rute pengiriman", show=True).add_to(m)
    for _, r in routes.sort_values("Alokasi (kg)").iterrows():
        s, d = r["Sumber"], r["Tujuan"]
        if s not in coords.index or d not in coords.index:
            continue
        used_nodes.update([s, d])
        p0 = (coords.loc[s, "lat"], coords.loc[s, "lon"]); p1 = (coords.loc[d, "lat"], coords.loc[d, "lon"])
        pts = arc(p0, p1)
        w = (1.6 + 8.0 * math.sqrt(r["Alokasi (kg)"] / fmax)) * width_scale
        if r["Terblokir"]:
            color = "#ffffff" if bg == "#0b0e14" else "#000000"
        elif color_mode.startswith("Sumber"):
            color = src_color.get(s, "#FFEA00")
        elif color_mode.startswith("Satu warna"):
            color = "#FFEA00" if bg == "#0b0e14" else "#E91E63"
        else:
            t = (math.log(max(r["Biaya (USD/kg)"], cmin)) - lmin) / (lmax - lmin) if lmax > lmin else 0.5
            color = gradient(t)
        biaya_txt = "rute terlarang (Big-M)" if r["Terblokir"] else f"{r['Biaya (USD/kg)']:.2f} USD/kg"
        tip = (f"<b>{html.escape(str(s))}</b> &rarr; <b>{html.escape(str(d))}</b><br>Alokasi: {fmt_int(r['Alokasi (kg)'])} kg<br>"
               f"Biaya: {biaya_txt}<br>Total: ${fmt_int(r['Biaya (USD)'])}")
        if animate and not r["Terblokir"]:
            plugins.AntPath(pts, color=color, pulse_color="#ffffff" if bg == "#0b0e14" else "#222222",
                            weight=w, opacity=0.9, delay=1400, dash_array=[10, 24], tooltip=tip).add_to(layer)
        else:
            folium.PolyLine(pts, color=color, weight=w, opacity=0.88 if not r["Terblokir"] else 0.9,
                            dash_array="6 8" if r["Terblokir"] else None, tooltip=tip).add_to(layer)

    smax = float(supply.max()) or 1.0
    dmax = float(demand.max()) or 1.0
    nodes_layer = folium.FeatureGroup(name="Node", show=True).add_to(m)
    outline = "#ffffff" if bg == "#0b0e14" else "#111111"
    for s in supply.index:
        if s in coords.index and s in used_nodes:
            folium.CircleMarker((coords.loc[s, "lat"], coords.loc[s, "lon"]), radius=5 + 9 * math.sqrt(supply[s] / smax),
                                color=outline, weight=1.5, fill=True, fill_color=SRC_COLOR, fill_opacity=0.95,
                                tooltip=f"<b>Sumber:</b> {html.escape(str(s))}<br>Supply: {fmt_int(supply[s])} kg").add_to(nodes_layer)
    for d in demand.index:
        if d in coords.index and d in used_nodes:
            folium.CircleMarker((coords.loc[d, "lat"], coords.loc[d, "lon"]), radius=4 + 8 * math.sqrt(demand[d] / dmax),
                                color=outline, weight=1.5, fill=True, fill_color=DST_COLOR, fill_opacity=0.95,
                                tooltip=f"<b>Tujuan:</b> {html.escape(str(d))}<br>Demand: {fmt_int(demand[d])} kg").add_to(nodes_layer)

    if used_nodes:
        sub = coords.loc[[n for n in used_nodes if n in coords.index]]
        m.fit_bounds([[sub["lat"].min() - 3, sub["lon"].min() - 5], [sub["lat"].max() + 3, sub["lon"].max() + 5]])

    txt = "#e8eaed" if bg == "#0b0e14" else "#202124"
    panel = "rgba(15,18,27,0.88)" if bg == "#0b0e14" else "rgba(255,255,255,0.92)"
    if color_mode.startswith("Biaya"):
        grad_css = ",".join(f"{gradient(t)} {int(t*100)}%" for t in [0, .2, .4, .6, .8, 1])
        legend_rows = (f"<div style='font-weight:600;margin-bottom:4px'>Biaya per kg</div>"
                       f"<div style='height:10px;width:170px;border-radius:5px;background:linear-gradient(90deg,{grad_css})'></div>"
                       f"<div style='display:flex;justify-content:space-between;font-size:11px;margin-top:2px'>"
                       f"<span>${cmin:,.2f}</span><span>${cmax:,.0f}</span></div>")
    elif color_mode.startswith("Sumber"):
        legend_rows = "<div style='font-weight:600'>Warna garis = sumber</div>"
    else:
        legend_rows = "<div style='font-weight:600'>Garis = rute teralokasi</div>"
    legend = f"""
    <div style="position:fixed;bottom:22px;left:12px;z-index:9999;background:{panel};color:{txt};
                padding:10px 12px;border-radius:10px;font-family:Arial,sans-serif;font-size:12px;
                box-shadow:0 2px 8px rgba(0,0,0,.45)">
      {legend_rows}
      <div style="margin-top:7px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{SRC_COLOR};border:1px solid {outline}"></span> Sumber
      &nbsp;<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{DST_COLOR};border:1px solid {outline}"></span> Tujuan</div>
      <div style="margin-top:4px;font-size:11px;opacity:.85">Tebal garis = volume (kg)</div>
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))
    return m
