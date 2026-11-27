from pathlib import Path
import numpy as np
import pandas as pd

EPS = 1e-9
BASE = Path(__file__).parent
DEFAULT_XLSX = BASE / "data" / "scms_data_model_transportasi.xlsx"
DEFAULT_COORD = BASE / "data" / "coordinates_filled.csv"


def read_workbook(src):
    xl = pd.ExcelFile(src)
    names = {s.lower(): s for s in xl.sheet_names}
    data = xl.parse(names["data_bersih"])
    data.columns = [str(c).strip() for c in data.columns]
    mat = xl.parse(names["matriks_biaya"], index_col=0)
    mat = mat[~mat.index.astype(str).str.lower().str.startswith("demand")]
    mat = mat.drop(columns=[c for c in mat.columns if str(c).lower().startswith("supply")])
    mat.columns = [str(c) for c in mat.columns]
    mat.index = [str(i) for i in mat.index]
    mat.index.name = "Sumber \\ Tujuan"
    mat = mat.apply(pd.to_numeric, errors="coerce")
    supply = data.groupby("sumber")["berat_kg"].sum().reindex(mat.index).fillna(0.0)
    demand = data.groupby("tujuan")["berat_kg"].sum().reindex(mat.columns).fillna(0.0)
    return data, mat, supply, demand


def read_coords(src):
    df = pd.read_csv(src)
    low = {c.lower().strip(): c for c in df.columns}

    def pick(options):
        for o in options:
            if o in low:
                return low[o]
        raise KeyError(f"Kolom {options} tidak ditemukan pada CSV koordinat")

    name = pick(["node", "name", "nama", "location", "lokasi"])
    lat = pick(["lat", "latitude"])
    lon = pick(["lon", "lng", "long", "longitude"])
    out = pd.DataFrame({"node": df[name].astype(str), "lat": pd.to_numeric(df[lat], errors="coerce"),
                        "lon": pd.to_numeric(df[lon], errors="coerce")})
    return out.dropna().drop_duplicates("node").set_index("node")


def nwcr(C, a, b):
    a = a.copy(); b = b.copy()
    X = np.zeros(C.shape); basic = np.zeros(C.shape, bool)
    m, n = C.shape; i = j = 0
    while i < m and j < n:
        q = min(a[i], b[j]); X[i, j] = q; basic[i, j] = True
        a[i] -= q; b[j] -= q
        ra = a[i] <= EPS; rb = b[j] <= EPS
        if ra and rb:
            if i < m - 1: i += 1
            else: j += 1
        elif ra: i += 1
        else: j += 1
    return X, basic


def _drop_line(a, b, i, j, rows, cols):
    if a[i] <= EPS and b[j] <= EPS:
        if rows.sum() > 1: rows[i] = False
        else: cols[j] = False
    elif a[i] <= EPS: rows[i] = False
    else: cols[j] = False


def _pick_cell(C, a, b, rows, cols, line=None):
    ri = np.where(rows)[0]; ci = np.where(cols)[0]
    if line is None:
        cand = [(C[i, j], -min(a[i], b[j]), i, j) for i in ri for j in ci]
    elif line[0] == "r":
        cand = [(C[line[1], j], -min(a[line[1]], b[j]), line[1], j) for j in ci]
    else:
        cand = [(C[i, line[1]], -min(a[i], b[line[1]]), i, line[1]) for i in ri]
    _, _, i, j = min(cand)
    return i, j


def lcm(C, a, b):
    a = a.copy(); b = b.copy()
    X = np.zeros(C.shape); basic = np.zeros(C.shape, bool)
    rows = np.ones(len(a), bool); cols = np.ones(len(b), bool)
    while rows.any() and cols.any():
        i, j = _pick_cell(C, a, b, rows, cols)
        q = min(a[i], b[j]); X[i, j] = q; basic[i, j] = True
        a[i] -= q; b[j] -= q
        _drop_line(a, b, i, j, rows, cols)
    return X, basic


def _penalties(C, rows, cols):
    ri = np.where(rows)[0]; ci = np.where(cols)[0]
    pr = {}; pc = {}
    for i in ri:
        v = np.sort(C[i, ci]); pr[i] = v[1] - v[0] if len(v) > 1 else v[0]
    for j in ci:
        v = np.sort(C[ri, j]); pc[j] = v[1] - v[0] if len(v) > 1 else v[0]
    return pr, pc


def vam(C, a, b):
    a = a.copy(); b = b.copy()
    X = np.zeros(C.shape); basic = np.zeros(C.shape, bool)
    rows = np.ones(len(a), bool); cols = np.ones(len(b), bool)
    while rows.any() and cols.any():
        pr, pc = _penalties(C, rows, cols)
        ir = max(pr, key=pr.get); ic = max(pc, key=pc.get)
        line = ("r", ir) if pr[ir] >= pc[ic] else ("c", ic)
        i, j = _pick_cell(C, a, b, rows, cols, line)
        q = min(a[i], b[j]); X[i, j] = q; basic[i, j] = True
        a[i] -= q; b[j] -= q
        _drop_line(a, b, i, j, rows, cols)
    return X, basic


def _uv(C, basic):
    m, n = C.shape
    u = np.full(m, np.nan); v = np.full(n, np.nan); u[0] = 0.0
    stack = [("r", 0)]
    while stack:
        t, k = stack.pop()
        if t == "r":
            for j in np.where(basic[k])[0]:
                if np.isnan(v[j]):
                    v[j] = C[k, j] - u[k]; stack.append(("c", j))
        else:
            for i in np.where(basic[:, k])[0]:
                if np.isnan(u[i]):
                    u[i] = C[i, k] - v[k]; stack.append(("r", i))
    return u, v


def _cycle(basic, i0, j0):
    parent = {("r", i0): None}
    queue = [("r", i0)]
    while queue:
        node = queue.pop(0)
        if node == ("c", j0): break
        t, k = node
        if t == "r":
            for j in np.where(basic[k])[0]:
                nx = ("c", j)
                if nx not in parent: parent[nx] = node; queue.append(nx)
        else:
            for i in np.where(basic[:, k])[0]:
                nx = ("r", i)
                if nx not in parent: parent[nx] = node; queue.append(nx)
    path = []; node = ("c", j0)
    while node is not None:
        path.append(node); node = parent[node]
    path = path[::-1]
    edges = []
    for p, q in zip(path[:-1], path[1:]):
        i = p[1] if p[0] == "r" else q[1]
        j = q[1] if q[0] == "c" else p[1]
        edges.append((i, j))
    return edges


def modi(C, X0, basic0, limit=5000):
    X = X0.copy(); basic = basic0.copy()
    hist = [float((X * C).sum())]
    for it in range(limit):
        u, v = _uv(C, basic)
        if np.isnan(u).any() or np.isnan(v).any():
            raise ValueError("Basis tidak terhubung")
        D = C - u[:, None] - v[None, :]
        D[basic] = 0.0
        k = int(np.argmin(D))
        if D.flat[k] >= -1e-9:
            return X, basic, it, hist, D
        i0, j0 = divmod(k, C.shape[1])
        edges = _cycle(basic, i0, j0)
        L = len(edges)
        minus = [edges[t] for t in range(L) if (L - 1 - t) % 2 == 0]
        plus = [edges[t] for t in range(L) if (L - 1 - t) % 2 == 1]
        theta = min(X[e] for e in minus)
        leaving = next(e for e in minus if X[e] <= theta + EPS)
        for e in minus: X[e] -= theta
        for e in plus: X[e] += theta
        X[i0, j0] = theta; X[leaving] = 0.0
        basic[leaving] = False; basic[i0, j0] = True
        hist.append(float((X * C).sum()))
    raise RuntimeError("Batas iterasi tercapai")


def solve_all(cost, supply, demand):
    blocked = cost.isna().values
    M = 10.0 * float(np.nanmax(cost.values))
    C = np.where(blocked, M, cost.values.astype(float))
    a = supply.values.astype(float); b = demand.values.astype(float)
    out = {"C": C, "blocked": blocked, "M": M, "methods": {}}
    for name, fn in [("NWC", nwcr), ("LCM", lcm), ("VAM", vam)]:
        X0, B0 = fn(C, a, b)
        X1, B1, it, hist, D = modi(C, X0, B0)
        out["methods"][name] = dict(X0=X0, B0=B0, X1=X1, B1=B1, iters=it, hist=hist,
                                    minD=float(D[~B1].min()))
    return out


def summarize(sol, actual_cost):
    C, blocked = sol["C"], sol["blocked"]
    rows = []
    for name, r in sol["methods"].items():
        X0, X1 = r["X0"], r["X1"]
        rows.append({
            "Metode": name,
            "Sel terblokir (awal)": int(((X0 > EPS) & blocked).sum()),
            "Kg di rute terblokir": float(X0[blocked].sum()),
            "Biaya awal valid (USD)": float((X0[~blocked] * C[~blocked]).sum()),
            "Biaya awal + Big-M (USD)": float((X0 * C).sum()),
            "Iterasi MODI": r["iters"],
            "Biaya akhir (USD)": float((X1 * C).sum()),
            "Sel terblokir (akhir)": int(((X1 > EPS) & blocked).sum()),
            "Rute teralokasi (akhir)": int((X1 > EPS).sum()),
            "Hemat vs aktual (%)": (1 - float((X1 * C).sum()) / actual_cost) * 100 if actual_cost else np.nan,
        })
    return pd.DataFrame(rows)


def routes_table(X, cost, C, blocked):
    idx = np.argwhere(X > EPS)
    rows = []
    for i, j in idx:
        rows.append({"Sumber": cost.index[i], "Tujuan": cost.columns[j], "Alokasi (kg)": float(X[i, j]),
                     "Biaya (USD/kg)": float(C[i, j]) if not blocked[i, j] else np.nan,
                     "Biaya (USD)": float(X[i, j] * C[i, j]), "Terblokir": bool(blocked[i, j])})
    df = pd.DataFrame(rows)
    return df.sort_values("Alokasi (kg)", ascending=False).reset_index(drop=True) if len(df) else df
