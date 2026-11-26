import io
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
import streamlit.components.v1 as components

import core
import mapviz

st.set_page_config(page_title="SCMS | Global Transportation Optimization", page_icon="🌍", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stMetric"]{background:#151a24;border:1px solid #262d3d;border-radius:12px;padding:14px 18px;}
    [data-testid="stMetricValue"]{font-size:1.85rem;font-weight:650;}
    [data-testid="stMetricLabel"]{opacity:.8;}
    h1{font-weight:800;letter-spacing:-.5px;}
    .app-sub{opacity:.65;font-size:.9rem;margin-top:-.8rem;margin-bottom:1.2rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def show_df(df, **kw):
    try:
        st.dataframe(df, width="stretch", **kw)
    except TypeError:
        st.dataframe(df, use_container_width=True, **kw)


def show_chart(ch):
    try:
        st.altair_chart(ch, width="stretch")
    except TypeError:
        st.altair_chart(ch, use_container_width=True)


@st.cache_data(show_spinner=False)
def load_default():
    data, cost, supply, demand = core.read_workbook(core.DEFAULT_XLSX)
    return data, cost, supply, demand, core.read_coords(core.DEFAULT_COORD)


@st.cache_data(show_spinner=False)
def load_xlsx_bytes(b):
    return core.read_workbook(io.BytesIO(b))


@st.cache_data(show_spinner=False)
def load_csv_bytes(b):
    return core.read_coords(io.BytesIO(b))


@st.cache_data(show_spinner="Menghitung NWC, LCM, VAM, dan MODI ...")
def run_solver(cost, supply, demand):
    return core.solve_all(cost, supply, demand)


# ------------------------------------------------------------------ sidebar
st.sidebar.markdown("### Data input")
with st.sidebar.expander("Ganti data (opsional)"):
    up_x = st.file_uploader("Upload SCMS Excel workbook", type=["xlsx"], key="up_x")
    up_c = st.file_uploader("Upload koordinat CSV", type=["csv"], key="up_c")

data, cost, supply, demand, coords = load_default()
source_label = "Data bawaan: SCMS Delivery History 2006-2015"
if up_x is not None:
    try:
        data, cost, supply, demand = load_xlsx_bytes(up_x.getvalue())
        source_label = f"Workbook upload: {up_x.name}"
    except Exception as e:
        st.sidebar.error(f"Workbook tidak terbaca: {e}")
if up_c is not None:
    try:
        coords = load_csv_bytes(up_c.getvalue())
    except Exception as e:
        st.sidebar.error(f"CSV koordinat tidak terbaca: {e}")
st.sidebar.caption(source_label)

st.sidebar.markdown("### Navigasi")
page = st.sidebar.radio("Navigasi", ["Overview", "Data Management", "Algorithm Analysis", "Distribution Map"],
                        label_visibility="collapsed")

n_src, n_dst = cost.shape
n_routes = int(cost.notna().sum().sum())
st.sidebar.markdown("---")
st.sidebar.caption(f"Sumber: {n_src} · Tujuan: {n_dst} · Rute tersedia: {n_routes}")

actual_cost = float(data["biaya_freight_usd"].sum())
sol = run_solver(cost, supply, demand)
summary = core.summarize(sol, actual_cost)
best_name = summary.loc[summary["Biaya akhir (USD)"].idxmin(), "Metode"]
final_cost = float(summary["Biaya akhir (USD)"].min())

st.title("SCMS | Global Transportation Optimization")
st.markdown('<div class="app-sub">Transportation model · NWC · LCM · VAM · MODI · OpenStreetMap</div>',
            unsafe_allow_html=True)

fmt_int = lambda x: f"{x:,.0f}"


def alloc_frame(X, highlight_blocked=True):
    df = pd.DataFrame(X, index=cost.index, columns=cost.columns)
    sty = df.style.format(lambda v: "" if abs(v) < 1e-9 else f"{v:,.0f}")
    if highlight_blocked:
        mask = pd.DataFrame(sol["blocked"] & (X > core.EPS), index=cost.index, columns=cost.columns)
        sty = sty.apply(lambda _: mask.map(lambda f: "background-color:#7a1f2b;color:#fff" if f else ""), axis=None)
    return sty


# ------------------------------------------------------------------ Overview
if page == "Overview":
    st.header("Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Node sumber", n_src)
    c2.metric("Node tujuan", n_dst)
    c3.metric("Rute teramati", f"{n_routes}", f"{n_routes / (n_src * n_dst):.1%} dari {n_src * n_dst} sel", delta_color="off")
    c4.metric("Total volume", f"{fmt_int(supply.sum())} kg")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Biaya aktual (freight)", f"${actual_cost:,.0f}")
    c2.metric("Biaya optimal (MODI)", f"${final_cost:,.2f}")
    c3.metric("Penghematan", f"${actual_cost - final_cost:,.0f}")
    c4.metric("Penghematan (%)", f"{(1 - final_cost / actual_cost) * 100:.2f}%")

    st.subheader("Supply dan demand")
    left, right = st.columns(2)
    sdf = supply.rename("kg").reset_index().rename(columns={"index": "Sumber"})
    sdf.columns = ["Sumber", "kg"]
    ddf = demand.rename("kg").reset_index()
    ddf.columns = ["Tujuan", "kg"]
    with left:
        ch = alt.Chart(sdf).mark_bar(color="#2979FF").encode(
            x=alt.X("kg:Q", title="Supply (kg)", scale=alt.Scale(type="sqrt")),
            y=alt.Y("Sumber:N", sort="-x", title=None),
            tooltip=["Sumber", alt.Tooltip("kg:Q", format=",.0f")]).properties(height=520, title="Supply per sumber (skala akar)")
        show_chart(ch)
    with right:
        top = ddf.sort_values("kg", ascending=False).head(15)
        ch = alt.Chart(top).mark_bar(color="#FF4B4B").encode(
            x=alt.X("kg:Q", title="Demand (kg)"),
            y=alt.Y("Tujuan:N", sort="-x", title=None),
            tooltip=["Tujuan", alt.Tooltip("kg:Q", format=",.0f")]).properties(height=520, title="15 negara tujuan dengan demand terbesar")
        show_chart(ch)

    st.subheader("Perbandingan metode")
    show_df(summary[["Metode", "Sel terblokir (awal)", "Biaya awal valid (USD)", "Iterasi MODI", "Biaya akhir (USD)",
                     "Hemat vs aktual (%)"]].style.format({"Biaya awal valid (USD)": "{:,.0f}", "Biaya akhir (USD)": "{:,.2f}",
                                                           "Hemat vs aktual (%)": "{:.2f}"}), hide_index=True)
    with st.expander("Tentang model"):
        st.markdown(
            "- **Sumber** = kelompok produsen atau gudang regional (SCMS RDC); **tujuan** = negara penerima.\n"
            "- **Supply/demand** = total berat pengiriman (kg), sehingga model otomatis berimbang.\n"
            "- **Biaya** = rata-rata tertimbang freight per kg pada tiap rute. Rute yang tidak pernah muncul diberi biaya Big-M.\n"
            "- **NWC, LCM, VAM** mencari solusi awal; **MODI** memperbaikinya sampai optimal."
        )

# ------------------------------------------------------------ Data Management
elif page == "Data Management":
    st.header("Data Management")
    t1, t2, t3 = st.tabs(["Shipment records", "Supply & demand", "Cost matrix"])
    with t1:
        c1, c2 = st.columns(2)
        fs = c1.multiselect("Filter sumber", list(cost.index))
        fd = c2.multiselect("Filter tujuan", list(cost.columns))
        view = data
        if fs: view = view[view["sumber"].isin(fs)]
        if fd: view = view[view["tujuan"].isin(fd)]
        m1, m2, m3 = st.columns(3)
        m1.metric("Pengiriman", fmt_int(len(view)))
        m2.metric("Total berat", f"{fmt_int(view['berat_kg'].sum())} kg")
        m3.metric("Total freight", f"${view['biaya_freight_usd'].sum():,.0f}")
        show_df(view.reset_index(drop=True), height=420)
    with t2:
        l, r = st.columns(2)
        with l:
            st.markdown("**Sumber (supply)**")
            show_df(supply.rename("Supply (kg)").reset_index().rename(columns={"index": "Sumber"}).style.format({"Supply (kg)": "{:,.0f}"}), hide_index=True, height=520)
        with r:
            st.markdown("**Tujuan (demand)**")
            show_df(demand.rename("Demand (kg)").reset_index().rename(columns={"index": "Tujuan"}).style.format({"Demand (kg)": "{:,.0f}"}), hide_index=True, height=520)
        balanced = np.isclose(supply.sum(), demand.sum())
        st.success(f"Total supply = {fmt_int(supply.sum())} kg, total demand = {fmt_int(demand.sum())} kg. "
                   + ("Model berimbang." if balanced else "Model tidak berimbang."))
    with t3:
        st.caption("Biaya dalam USD/kg sesuai matriks biaya pada workbook. Sel kosong berarti rute tidak pernah muncul di data (dilarang).")
        show_df(cost.style.format("{:.4f}", na_rep="None"), height=560)

# ----------------------------------------------------------- Algorithm Analysis
elif page == "Algorithm Analysis":
    st.header("Algorithm Analysis")
    method = st.radio("Metode solusi awal", ["NWC", "LCM", "VAM"], horizontal=True, index=2)
    r = sol["methods"][method]
    C, blocked = sol["C"], sol["blocked"]
    row = summary[summary["Metode"] == method].iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sel terblokir (awal)", int(row["Sel terblokir (awal)"]))
    c2.metric("Biaya awal (rute valid)", f"${row['Biaya awal valid (USD)']:,.0f}")
    c3.metric("Iterasi MODI", int(row["Iterasi MODI"]))
    c4.metric("Biaya akhir", f"${row['Biaya akhir (USD)']:,.2f}")
    t1, t2, t3, t4 = st.tabs(["Solusi awal", "Iterasi MODI", "Alokasi akhir", "Perbandingan"])
    with t1:
        st.caption("Alokasi (kg). Sel merah = alokasi pada rute terlarang (Big-M). Sel kosong = 0.")
        show_df(alloc_frame(r["X0"]), height=560)
    with t2:
        hist = pd.DataFrame({"Iterasi": range(len(r["hist"])), "Biaya total (USD, termasuk Big-M)": r["hist"]})
        hist["Penurunan"] = hist["Biaya total (USD, termasuk Big-M)"].diff().fillna(0)
        ch = alt.Chart(hist).mark_line(point=True, color="#FFB300").encode(
            x=alt.X("Iterasi:Q"), y=alt.Y("Biaya total (USD, termasuk Big-M):Q", scale=alt.Scale(type="log")),
            tooltip=["Iterasi", alt.Tooltip("Biaya total (USD, termasuk Big-M):Q", format=",.2f")]).properties(height=320)
        show_chart(ch)
        show_df(hist.style.format({"Biaya total (USD, termasuk Big-M)": "{:,.2f}", "Penurunan": "{:,.2f}"}), hide_index=True, height=300)
    with t3:
        st.caption(f"Solusi optimal dari {method} setelah MODI. Reduced cost terkecil sel non-basis = {r['minD']:.4f}.")
        show_df(alloc_frame(r["X1"], highlight_blocked=False), height=560)
        routes = core.routes_table(r["X1"], cost, C, blocked)
        show_df(routes.style.format({"Alokasi (kg)": "{:,.0f}", "Biaya (USD/kg)": "{:.2f}", "Biaya (USD)": "{:,.0f}"}), hide_index=True, height=360)
    with t4:
        show_df(summary.style.format({"Kg di rute terblokir": "{:,.0f}", "Biaya awal valid (USD)": "{:,.0f}", "Biaya awal + Big-M (USD)": "{:,.0f}",
                                      "Biaya akhir (USD)": "{:,.2f}", "Hemat vs aktual (%)": "{:.2f}"}), hide_index=True)
        frames = []
        for k, v in sol["methods"].items():
            frames.append(pd.DataFrame({"Iterasi": range(len(v["hist"])), "Biaya": v["hist"], "Metode": k}))
        allh = pd.concat(frames)
        ch = alt.Chart(allh).mark_line(point=True).encode(
            x="Iterasi:Q", y=alt.Y("Biaya:Q", scale=alt.Scale(type="log"), title="Biaya total (USD, termasuk Big-M)"),
            color=alt.Color("Metode:N", scale=alt.Scale(domain=["NWC", "LCM", "VAM"], range=["#FF4B4B", "#FFB300", "#00E676"])),
            tooltip=["Metode", "Iterasi", alt.Tooltip("Biaya:Q", format=",.2f")]).properties(height=340)
        show_chart(ch)
        same = np.allclose(summary["Biaya akhir (USD)"], summary["Biaya akhir (USD)"].iloc[0])
        st.info("Ketiga metode berakhir pada biaya optimal yang sama." if same else "Biaya akhir ketiga metode berbeda; periksa data.")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            summary.to_excel(w, sheet_name="Ringkasan", index=False)
            for k, v in sol["methods"].items():
                pd.DataFrame(v["X0"], index=cost.index, columns=cost.columns).to_excel(w, sheet_name=f"{k}_awal")
                pd.DataFrame(v["X1"], index=cost.index, columns=cost.columns).to_excel(w, sheet_name=f"{k}_MODI")
        st.download_button("Unduh hasil (Excel)", buf.getvalue(), "hasil_nwc_lcm_vam_modi.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ------------------------------------------------------------ Distribution Map
else:
    st.header("Distribution Map")
    missing = [n for n in list(cost.index) + list(cost.columns) if n not in coords.index]
    if missing:
        st.warning("Koordinat belum ada untuk: " + ", ".join(missing))
    c1, c2, c3 = st.columns([1.3, 1.3, 1.4])
    options = ["Hasil akhir MODI", "Solusi awal NWC", "Solusi awal LCM", "Solusi awal VAM"]
    choice = c1.selectbox("Solusi yang ditampilkan", options)
    tile_name = c2.selectbox("Peta dasar", list(mapviz.TILES.keys()))
    color_mode = c3.selectbox("Warna garis", ["Biaya per kg (gradasi)", "Sumber (warna per sumber)", "Satu warna (kuning terang)"])
    c1, c2, c3, c4 = st.columns([1.3, 1.3, 1.0, 0.8])
    srcs = c1.multiselect("Filter sumber", list(cost.index))
    dsts = c2.multiselect("Filter tujuan", list(cost.columns))
    wscale = c3.slider("Tebal garis", 0.5, 2.0, 1.0, 0.1)
    animate = c4.checkbox("Animasi aliran", value=False)

    if choice == "Hasil akhir MODI":
        X = sol["methods"][best_name]["X1"]
    else:
        X = sol["methods"][choice.split()[-1]]["X0"]
    routes_all = core.routes_table(X, cost, sol["C"], sol["blocked"])
    routes = routes_all
    if srcs: routes = routes[routes["Sumber"].isin(srcs)]
    if dsts: routes = routes[routes["Tujuan"].isin(dsts)]

    shown_cost = float(routes["Biaya (USD)"].sum()) if len(routes) else 0.0
    label = "Final MODI cost" if (choice == "Hasil akhir MODI" and not srcs and not dsts) else "Total cost (rute terlihat)"
    m1, m2, m3 = st.columns(3)
    m1.metric(label, f"${shown_cost:,.2f}" if (not srcs and not dsts and choice == "Hasil akhir MODI") else f"${shown_cost:,.0f}")
    m2.metric("Allocated volume", f"{fmt_int(routes['Alokasi (kg)'].sum() if len(routes) else 0)} kg")
    m3.metric("Allocated routes", int(len(routes)))
    if choice != "Hasil akhir MODI" and len(routes_all) and routes_all["Terblokir"].any():
        st.warning(f"{int(routes_all['Terblokir'].sum())} rute pada solusi awal ini melewati rute terlarang (Big-M); digambar putus-putus.")

    fmap = mapviz.build_map(routes, coords, supply, demand, tile_name, color_mode=color_mode,
                            animate=animate, width_scale=wscale, source_order=list(cost.index))
    html_map = fmap.get_root().render()
    if hasattr(st, "iframe"):
        st.iframe(html_map, height=660)
    else:
        components.html(html_map, height=660, scrolling=False)
    st.caption("Peta dasar: © OpenStreetMap contributors. Koordinat node bersifat perkiraan pusat kota/negara.")
    with st.expander("Tabel rute"):
        show_df(routes.style.format({"Alokasi (kg)": "{:,.0f}", "Biaya (USD/kg)": "{:.2f}", "Biaya (USD)": "{:,.0f}"}), hide_index=True)
        st.download_button("Unduh rute (CSV)", routes.to_csv(index=False).encode(), "rute_distribusi.csv", "text/csv")
