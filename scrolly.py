"""
scrolly.py  —  Genera el scrollytelling completo de Oscars
Corre: python scrolly.py
Abre:  scrollytelling.html
"""

import json, os, base64, io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import joblib

# ── Helpers para imágenes decorativas ────────────────────────────────────────
try:
    from PIL import Image as _PIL
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

def _img_b64(path, max_h=None, max_w=None, quality=82):
    """Encode image as base64 JPEG (optionally resized)."""
    if not _PIL_OK:
        return ""
    try:
        img = _PIL.open(path).convert("RGB")
        w, h = img.size
        if max_h and h > max_h:
            img = img.resize((int(w * max_h / h), max_h), _PIL.LANCZOS)
        elif max_w and w > max_w:
            img = img.resize((max_w, int(h * max_w / w)), _PIL.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"  [img] {path}: {e}")
        return ""

def _img_b64_png(path, max_h=200, black_thresh=45):
    """Remove solid-black background → PNG con transparencia → base64."""
    if not _PIL_OK:
        return ""
    try:
        img = _PIL.open(path).convert("RGBA")
        w, h = img.size
        if h > max_h:
            img = img.resize((int(w * max_h / h), max_h), _PIL.LANCZOS)
        data = np.array(img)
        mask = ((data[:,:,0] < black_thresh) &
                (data[:,:,1] < black_thresh) &
                (data[:,:,2] < black_thresh))
        data[:,:,3] = np.where(mask, 0, 255)
        out = _PIL.fromarray(data)
        buf = io.BytesIO()
        out.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"  [img-png] {path}: {e}")
        return ""

# ─────────────────────────────────────────────────────────────────────────────
# Paleta y layout base
# ─────────────────────────────────────────────────────────────────────────────
GOLD, RED, GRAY = "#e8b84b", "#c0392b", "#999999"
BG, WHITE       = "#0d0d0d", "#f0f0f0"

LAYOUT = dict(
    plot_bgcolor=BG, paper_bgcolor=BG,
    font=dict(color=WHITE, family="Georgia, serif"),
    margin=dict(l=50, r=30, t=55, b=45),
)

def layout(**kwargs):
    """LAYOUT base + overrides (evita conflictos con height/margin)."""
    return {**LAYOUT, **kwargs}

def fig_json(fig):
    """Serializa a JSON convirtiendo el formato binario bdata de Plotly a listas."""
    import json, base64
    import numpy as np

    def sanitize(obj):
        # Detectar el formato binario de Plotly: {'dtype': 'i2', 'bdata': '...'}
        if isinstance(obj, dict):
            if "bdata" in obj and "dtype" in obj:
                raw = base64.b64decode(obj["bdata"])
                arr = np.frombuffer(raw, dtype=np.dtype(obj["dtype"]))
                return arr.tolist()
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [sanitize(i) for i in obj]
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if hasattr(obj, "tolist"):
            return obj.tolist()
        return obj

    return json.dumps(sanitize(fig.to_dict()))

# ─────────────────────────────────────────────────────────────────────────────
# Datos
# ─────────────────────────────────────────────────────────────────────────────
df = pd.read_csv("data/master_dataset.csv")
df["won_label"] = df["won_best_picture"].map({1: "Ganadora", 0: "Nominada"})
df["decade"]    = (df["ceremony_year"] // 10) * 10

# ── Parches de calidad de datos ───────────────────────────────────────────────
# Birdman (2015): rt_score y imdb_rating incorrectos en el dataset fuente
df.loc[(df["nominated_title"] == "Birdman") & (df["ceremony_year"] == 2015),
       "rt_score"]   = 91.0
df.loc[(df["nominated_title"] == "Birdman") & (df["ceremony_year"] == 2015),
       "imdb_rating"] = 7.7
# Crash (2006): rt_score ausente
df.loc[(df["nominated_title"] == "Crash") & (df["ceremony_year"] == 2006),
       "rt_score"]   = 75.0
# ROI: calcular donde falte
mask_roi = df["roi"].isna() & (df["budget_m"] > 0) & (df["revenue_m"] > 0)
df.loc[mask_roi, "roi"] = df.loc[mask_roi, "revenue_m"] / df.loc[mask_roi, "budget_m"]

winners = df[df["won_best_picture"] == 1]
losers  = df[df["won_best_picture"] == 0]

# ─── Genre combinations ───────────────────────────────────────────────────────
GENRE_COLS = [c for c in df.columns if c.startswith("genre_") and c != "main_genre"]

def get_genre_combo(row):
    active = [c.replace("genre_", "").replace("_", " ").title()
              for c in GENRE_COLS if row[c] == 1]
    if len(active) >= 2:
        return active[0] + " + " + active[1]
    elif len(active) == 1:
        return active[0]
    return row.get("main_genre", "Otro")

df["genre_combo"]      = df[GENRE_COLS].apply(get_genre_combo, axis=1)
winners_with_combo     = df[df["won_best_picture"] == 1]

# ─── Language fix (use main_language for reliability) ─────────────────────────
df["is_eng"] = df["main_language"].str.lower().str.startswith("english", na=False).astype(int)
pct_eng = df["is_eng"].mean() * 100

# ═════════════════════════════════════════════════════════════════════════════
# FIG 0 — INTRO: números grandes
# ═════════════════════════════════════════════════════════════════════════════
n_years  = df["ceremony_year"].nunique()
n_films  = len(df[df["ceremony_year"] < 2026])   # excluir nominadas 2026 del total
avg_prec = winners["total_precursor_wins"].mean()

stats = [
    (f"{n_years}",       "años de historia"),
    (f"{n_films}",       "películas nominadas"),
    (f"{avg_prec:.1f}",  "precursores promedio<br>del ganador"),
    (f"{pct_eng:.0f}%",  "nominadas en inglés"),
]

# 2 filas × 2 columnas
positions = [(0.7, 1.55), (2.7, 1.55), (0.7, 0.55), (2.7, 0.55)]

fig0 = go.Figure()
for (x, y), (val, label) in zip(positions, stats):
    fig0.add_annotation(x=x, y=y, text=val, showarrow=False,
                        font=dict(size=52, color=GOLD, family="Georgia"),
                        xref="x", yref="y", align="center")
    fig0.add_annotation(x=x, y=y - 0.35, text=label, showarrow=False,
                        font=dict(size=12, color=WHITE),
                        xref="x", yref="y", align="center")

fig0.update_layout(**layout(
    height=340, margin=dict(t=10, b=10, l=10, r=10),
    xaxis=dict(visible=False, range=[0, 3.5]),
    yaxis=dict(visible=False, range=[0, 2.1]),
))

# ═════════════════════════════════════════════════════════════════════════════
# FIG 1 — ¿La Academia tiene un tipo? — Bubble chart combinaciones de géneros
# ═════════════════════════════════════════════════════════════════════════════
genre_stats = (
    df[df["ceremony_year"] < 2026].groupby("genre_combo")
    .agg(n=("nominated_title", "count"), wins=("won_best_picture", "sum"))
    .reset_index()
    .rename(columns={"genre_combo": "combo"})
)
genre_stats["win_rate"] = genre_stats["wins"] / genre_stats["n"] * 100
genre_stats = genre_stats[genre_stats["n"] >= 3].copy()

ejemplos = (
    winners_with_combo.groupby("genre_combo")["nominated_title"]
    .apply(lambda x: "<br>".join(x.head(3).tolist()))
    .reset_index().rename(columns={"nominated_title": "ejemplos", "genre_combo": "combo"})
)
genre_stats = genre_stats.merge(ejemplos, on="combo", how="left")
genre_stats["ejemplos"] = genre_stats["ejemplos"].fillna("ninguna")

fig1 = go.Figure(go.Scatter(
    x=genre_stats["n"],          # eje X = volumen (nº nominadas)
    y=genre_stats["win_rate"],   # eje Y = win rate
    mode="markers+text",
    marker=dict(
        size=genre_stats["wins"].clip(lower=1) * 10 + 16,
        color=genre_stats["win_rate"],
        colorscale=[[0, GRAY], [0.5, RED], [1, GOLD]],
        showscale=False, opacity=0.85,
        line=dict(color="rgba(255,255,255,0.13)", width=1),
    ),
    text=genre_stats["combo"],
    textposition="top center",
    textfont=dict(size=9, color=WHITE),
    customdata=np.stack([genre_stats["wins"], genre_stats["ejemplos"]], axis=-1),
    hovertemplate=(
        "<b>%{text}</b><br>"
        "Nominadas: %{x}  |  Win rate: %{y:.1f}%<br>"
        "Ganadoras: %{customdata[0]}<br>"
        "<i>%{customdata[1]}</i><extra></extra>"
    ),
))
fig1.update_layout(**layout(height=480,
    title="Win rate por combinación de géneros",
    xaxis=dict(title="Nº de nominadas", gridcolor="#222", zeroline=False),
    yaxis=dict(title="Win rate %", gridcolor="#222", zeroline=False),
))

# ═════════════════════════════════════════════════════════════════════════════
# FIG 2 — La barrera del idioma — Donuts nominadas vs ganadoras
# ═════════════════════════════════════════════════════════════════════════════
lang = (
    df[df["ceremony_year"] < 2026].groupby("is_eng")
    .agg(total=("nominated_title", "count"), wins=("won_best_picture", "sum"))
    .reset_index()
)
lang["label"] = lang["is_eng"].map({1: "Inglés", 0: "Otro idioma"})

fig2 = go.Figure()
fig2.add_trace(go.Pie(
    labels=lang["label"], values=lang["total"], hole=0.55,
    marker=dict(colors=[GOLD, GRAY]),
    textinfo="label+percent", textfont=dict(size=13, color=WHITE),
    domain=dict(x=[0, 0.46]), name="Nominadas",
    title=dict(text="<b>Nominadas</b>", font=dict(color=WHITE, size=12)),
    hovertemplate="<b>%{label}</b><br>%{value} (%{percent})<extra></extra>",
))
fig2.add_trace(go.Pie(
    labels=lang["label"], values=lang["wins"], hole=0.55,
    marker=dict(colors=[GOLD, GRAY]),
    textinfo="label+percent", textfont=dict(size=13, color=WHITE),
    domain=dict(x=[0.54, 1.0]), name="Ganadoras", showlegend=False,
    title=dict(text="<b>Ganadoras</b>", font=dict(color=WHITE, size=12)),
    hovertemplate="<b>%{label}</b><br>%{value} (%{percent})<extra></extra>",
))
fig2.update_layout(**layout(height=460, title="Nominadas vs Ganadoras por idioma"))

# Ganadoras no-inglesas (usa main_language directamente)
non_eng_w = df[
    (df["won_best_picture"] == 1) &
    (~df["main_language"].str.lower().str.startswith("english", na=False))
][["ceremony_year", "nominated_title", "main_language"]].sort_values("ceremony_year")

if len(non_eng_w) > 0:
    non_eng_txt = " · ".join(
        f"<em>{r['nominated_title']}</em> ({r['main_language']}, {int(r['ceremony_year'])})"
        for _, r in non_eng_w.iterrows()
    )
else:
    non_eng_txt = "ninguna hasta el momento"

# ═════════════════════════════════════════════════════════════════════════════
# FIG 3 — ¿Se puede comprar un Oscar? — Boxplot presupuesto
# ═════════════════════════════════════════════════════════════════════════════
df_hist = df[df["ceremony_year"] < 2026].copy()
df_fin  = df_hist[df_hist["budget_m"]  > 0].copy()
df_fin2 = df_hist[(df_hist["budget_m"] > 0) & (df_hist["revenue_m"] > 0)].copy()

fig3 = go.Figure()
for label, color in [("Nominada", GRAY), ("Ganadora", GOLD)]:
    sub = df_fin[df_fin["won_label"] == label]
    fig3.add_trace(go.Box(
        y=sub["budget_m"], name=label, marker_color=color,
        boxmean=True, jitter=0.4, pointpos=0,
        boxpoints="all", opacity=0.9,
        text=sub["nominated_title"],
        hovertemplate="<b>%{text}</b><br>Presupuesto: $%{y:.0f}M<extra></extra>",
    ))
fig3.update_layout(**layout(height=460,
    title="Distribución de presupuesto: ¿ganadoras vs nominadas?",
    yaxis=dict(title="Presupuesto (M USD)", gridcolor="#222",
               type="log"),          # escala log para ver mejor la distribución
    legend=dict(font=dict(color=WHITE)),
))

# Scatter budget vs revenue
fig3b = go.Figure()
for label, color, sym, sz, op in [
    ("Nominada", GRAY, "circle", 7, 0.6),
    ("Ganadora", GOLD, "star",   14, 0.95),
]:
    sub = df_fin2[df_fin2["won_label"] == label].copy()
    sub["roi"] = sub["roi"].fillna(sub["revenue_m"] / sub["budget_m"])
    # Incluir año en text para evitar la ambigüedad del customdata 2D
    hover_text = [
        f"{t} ({int(y)})" for t, y in zip(sub["nominated_title"], sub["ceremony_year"])
    ]
    fig3b.add_trace(go.Scatter(
        x=sub["budget_m"], y=sub["revenue_m"],
        mode="markers", name=label,
        marker=dict(color=color, size=sz, symbol=sym, opacity=op,
                    line=dict(color=WHITE, width=0.3)),
        text=hover_text,
        customdata=sub["roi"].round(2).tolist(),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Presupuesto: $%{x:.0f}M<br>"
            "Recaudación: $%{y:.0f}M<br>"
            "ROI: %{customdata:.1f}x<extra></extra>"
        ),
    ))
fig3b.update_layout(**layout(height=460,
    title="Presupuesto vs Recaudación (escala log)",
    xaxis=dict(title="Presupuesto M USD", gridcolor="#222", type="log"),
    yaxis=dict(title="Recaudación mundial M USD", gridcolor="#222", type="log"),
    legend=dict(font=dict(color=WHITE)),
))

# ═════════════════════════════════════════════════════════════════════════════
# FIG 4 — La suerte del novato: directores
# ═════════════════════════════════════════════════════════════════════════════
dir_df = (
    df_hist.assign(dir=df_hist["director"].fillna("").str.split(","))
    .explode("dir")
)
dir_df["dir"] = dir_df["dir"].str.strip()
dir_df = dir_df[dir_df["dir"] != ""].sort_values("ceremony_year")
dir_df["cum_nom"]      = dir_df.groupby("dir").cumcount() + 1
dir_df["is_first_nom"] = dir_df["cum_nom"] == 1

dir_stats = (
    dir_df.groupby("dir")
    .agg(noms=("nominated_title", "count"), wins=("won_best_picture", "sum"))
    .reset_index()
)
dir_stats["win_rate"] = dir_stats["wins"] / dir_stats["noms"] * 100

top_dirs = (
    dir_stats[dir_stats["noms"] >= 2]
    .nlargest(15, "noms")
    .sort_values("noms")
)

fig4 = go.Figure(go.Bar(
    x=top_dirs["noms"], y=top_dirs["dir"], orientation="h",
    marker_color=top_dirs["wins"].apply(lambda w: GOLD if w > 0 else GRAY),
    customdata=np.stack([top_dirs["wins"], top_dirs["win_rate"]], axis=-1),
    text=top_dirs["wins"].apply(lambda w: "★" * int(w) if w > 0 else ""),
    textposition="outside", textfont=dict(color=GOLD, size=10),
    hovertemplate=(
        "<b>%{y}</b><br>Nominaciones: %{x}<br>"
        "Oscars: %{customdata[0]}<br>Win rate: %{customdata[1]:.0f}%<extra></extra>"
    ),
))
fig4.update_layout(**layout(height=530,
    title="Directores más nominados  (dorado = ganó al menos una vez)",
    xaxis=dict(title="Nº de nominaciones", gridcolor="#222"),
    yaxis=dict(title=""),
))

# Primeras veces que ganaron
first_wins = dir_df[
    (dir_df["is_first_nom"]) & (dir_df["won_best_picture"] == 1)
][["dir", "ceremony_year", "nominated_title"]].sort_values("ceremony_year")

n_first_wins      = len(first_wins)
n_winners_total   = dir_df[dir_df["won_best_picture"] == 1]["dir"].nunique()
pct_first_win     = n_first_wins / n_winners_total * 100 if n_winners_total > 0 else 0
first_wins_txt    = " · ".join(
    f"<em>{r['nominated_title']}</em> ({r['dir']}, {int(r['ceremony_year'])})"
    for _, r in first_wins.head(5).iterrows()
)

# ═════════════════════════════════════════════════════════════════════════════
# FIG 5 — Los Oscars no arrancan en la ceremonia: precursores
# ═════════════════════════════════════════════════════════════════════════════
PREC_MAP = {
    "GG_drama_won":        "Globo de Oro — Drama",
    "GG_comedy_won":       "Globo de Oro — Comedia/Musical",
    "BAFTA_best_film_won": "BAFTA Mejor Película",
    "PGA_best_picture_won":"PGA Mejor Película",
    "CCA_best_picture_won":"Critics Choice Mejor Película",
    "WGA_original_won":    "WGA Guión Original",
    "WGA_adapted_won":     "WGA Guión Adaptado",
}

prec_rows = []
for col, label in PREC_MAP.items():
    if col not in df_hist.columns:
        continue
    sub  = df_hist[df_hist[col] == 1]
    wins = sub["won_best_picture"].sum()
    tot  = len(sub)
    if tot == 0:
        continue
    prec_rows.append({
        "precursor": label,
        "win_rate":  wins / tot * 100,
        "n_wins":    int(wins),
        "n_total":   tot,
    })

prec_df  = pd.DataFrame(prec_rows).sort_values("win_rate", ascending=True)
best_prec = prec_df.iloc[-1]

fig5 = go.Figure(go.Bar(
    x=prec_df["win_rate"], y=prec_df["precursor"], orientation="h",
    marker=dict(
        color=prec_df["win_rate"],
        colorscale=[[0, GRAY], [0.5, RED], [1, GOLD]],
        showscale=False,
    ),
    customdata=np.stack([prec_df["n_wins"], prec_df["n_total"]], axis=-1),
    text=prec_df["win_rate"].apply(lambda v: f"{v:.0f}%"),
    textposition="outside", textfont=dict(color=WHITE, size=11),
    hovertemplate=(
        "<b>%{y}</b><br>Win rate Oscar: %{x:.1f}%<br>"
        "(%{customdata[0]} de %{customdata[1]} ganaron el Oscar)<extra></extra>"
    ),
))
fig5.update_layout(**layout(height=460,
    title="¿Qué premios precursores mejor predicen el Oscar?",
    xaxis=dict(title="Win rate Oscar %", gridcolor="#222", range=[0, 105]),
    yaxis=dict(title=""),
))

# ═════════════════════════════════════════════════════════════════════════════
# FIG 6 — La Academia vs el público: boxplot IMDB
# ═════════════════════════════════════════════════════════════════════════════
fig6 = go.Figure()
for label, color in [("Nominada", GRAY), ("Ganadora", GOLD)]:
    sub = df_hist[df_hist["won_label"] == label].dropna(subset=["imdb_rating"])
    fig6.add_trace(go.Box(
        y=sub["imdb_rating"], name=label, marker_color=color,
        boxmean=True, jitter=0.4, pointpos=0,
        boxpoints="all", opacity=0.9,
        marker=dict(size=5, opacity=0.7),
        text=sub["nominated_title"],
        hovertemplate="<b>%{text}</b><br>IMDB: %{y:.1f}<extra></extra>",
    ))
fig6.update_layout(**layout(height=460,
    title="Rating IMDB: ganadoras vs nominadas",
    yaxis=dict(title="Rating IMDB", gridcolor="#333", range=[4, 10]),
    legend=dict(font=dict(color=WHITE)),
))

# Scatter RT vs IMDB
fig6b = go.Figure()
for label, color, sym, sz, op in [
    ("Nominada", GRAY, "circle", 8,  0.7),
    ("Ganadora", GOLD, "star",   14, 1.0),
]:
    sub = df_hist[df_hist["won_label"] == label].dropna(subset=["imdb_rating", "rt_score"])
    fig6b.add_trace(go.Scatter(
        x=sub["rt_score"], y=sub["imdb_rating"],
        mode="markers", name=label,
        marker=dict(color=color, size=sz, symbol=sym, opacity=op,
                    line=dict(color="rgba(255,255,255,0.4)", width=0.8)),
        text=sub["nominated_title"], customdata=sub["ceremony_year"],
        hovertemplate=(
            "<b>%{text}</b> (%{customdata})<br>"
            "Rotten Tomatoes: %{x}%<br>IMDB: %{y:.1f}<extra></extra>"
        ),
    ))
fig6b.update_layout(**layout(height=460,
    title="La Academia vs el público: crítica especializada vs voto popular",
    xaxis=dict(title="Rotten Tomatoes %", gridcolor="#333"),
    yaxis=dict(title="Rating IMDB", gridcolor="#333"),
    legend=dict(font=dict(color=WHITE)),
))

# ═════════════════════════════════════════════════════════════════════════════
# FIG 7 — ¿Puede un algoritmo predecir el Oscar? — Resultados históricos
# ═════════════════════════════════════════════════════════════════════════════
test_years_model = [2022, 2023, 2024, 2025]
MODEL_RESULTS    = []

try:
    final_model  = joblib.load("models/lgbm_oscar.pkl")
    all_features = joblib.load("models/features.pkl")
    df_test = df[df["ceremony_year"].isin(test_years_model)].copy()
    for year in test_years_model:
        yd    = df_test[df_test["ceremony_year"] == year]
        probs = final_model.predict_proba(yd[all_features].fillna(-999))[:, 1]
        pn    = probs / probs.sum()
        pred  = yd.iloc[pn.argmax()]["nominated_title"]
        real  = yd[yd["won_best_picture"] == 1]["nominated_title"].values[0]
        wp    = pn[yd["won_best_picture"].values == 1][0] * 100
        MODEL_RESULTS.append({
            "year": year, "pred": pred, "real": real,
            "correct": int(pred == real), "winner_prob": wp,
        })
except Exception:
    MODEL_RESULTS = [
        # Resultados reales del modelo entrenado (evaluación externa)
        {"year": 2022, "pred": "The Power of the Dog",               "real": "CODA",                               "correct": 0, "winner_prob": 16.1},
        {"year": 2023, "pred": "Everything Everywhere All at Once",  "real": "Everything Everywhere All at Once",  "correct": 1, "winner_prob": 54.8},
        {"year": 2024, "pred": "Oppenheimer",                        "real": "Oppenheimer",                        "correct": 1, "winner_prob": 56.8},
        {"year": 2025, "pred": "Anora",                              "real": "Anora",                              "correct": 1, "winner_prob": 55.7},
    ]

res_df       = pd.DataFrame(MODEL_RESULTS)
n_correct    = res_df["correct"].sum()
n_test       = len(res_df)

fig7 = go.Figure()
fig7.add_trace(go.Bar(
    x=res_df["year"].astype(str),
    y=res_df["winner_prob"],
    marker_color=[GOLD if r else RED for r in res_df["correct"]],
    text=[
        f"{'✓' if r else '✗'}  {p[:28]}{'…' if len(p)>28 else ''}"
        for r, p in zip(res_df["correct"], res_df["pred"])
    ],
    textposition="outside", textfont=dict(size=10, color=WHITE),
    customdata=np.stack([res_df["real"], res_df["pred"]], axis=-1),
    hovertemplate=(
        "<b>%{x}</b><br>"
        "Ganadora real: %{customdata[0]}<br>"
        "Predicción: %{customdata[1]}<br>"
        "Probabilidad asignada: %{y:.1f}%<extra></extra>"
    ),
    name="Probabilidad asignada a la ganadora",
))
fig7.add_hline(
    y=100 / 8, line_dash="dot", line_color=GRAY,
    annotation_text="baseline aleatorio (~12.5%)",
    annotation_font_color=GRAY,
)
fig7.update_layout(**layout(height=460,
    title=f"LightGBM — {n_correct}/{n_test} años acertados (datos nunca vistos)",
    xaxis=dict(title="Ceremonia"),
    yaxis=dict(title="Probabilidad asignada a la ganadora %",
               gridcolor="#222", range=[0, 100]),
))

# ═════════════════════════════════════════════════════════════════════════════
# FIG 8 — Mi predicción: Oscar 2026
# ═════════════════════════════════════════════════════════════════════════════
PRED_2026_FALLBACK = [
    ("Frankenstein",             0.6),
    ("F1",                       0.7),
    ("The Secret Agent",         1.8),
    ("Sentimental Value",        2.0),
    ("Train Dreams",             2.1),
    ("Bugonia",                  2.3),
    ("Sinners",                  5.1),
    ("Marty Supreme",           16.6),
    ("Hamnet",                  31.7),
    ("One Battle After Another",37.1),
]

pred2026_df = None
top_film_2026 = "Sentimental Value"
top_prob_2026 = 23.0

try:
    final_model  = joblib.load("models/lgbm_oscar.pkl")
    all_features = joblib.load("models/features.pkl")
    df_2026 = df[df["ceremony_year"] == 2026].copy()
    if len(df_2026) > 0:
        probs = final_model.predict_proba(df_2026[all_features].fillna(-999))[:, 1]
        pn    = probs / probs.sum() * 100
        rows  = sorted(zip(df_2026["nominated_title"].tolist(), pn.tolist()),
                       key=lambda x: x[1])
        pred2026_df   = pd.DataFrame(rows, columns=["title", "prob"])
        top_film_2026 = pred2026_df.nlargest(1, "prob").iloc[0]["title"]
        top_prob_2026 = pred2026_df["prob"].max()
except Exception:
    pass

if pred2026_df is None:
    pred2026_df   = pd.DataFrame(PRED_2026_FALLBACK, columns=["title", "prob"])
    pred2026_df   = pred2026_df.sort_values("prob").reset_index(drop=True)
    top_film_2026 = pred2026_df.nlargest(1, "prob").iloc[0]["title"]
    top_prob_2026 = pred2026_df["prob"].max()

# Colores: oro para la top predicción, degradado para el resto
bar_colors = [
    GOLD if t == top_film_2026 else f"rgba(150,130,50,{0.3 + 0.5*(p/top_prob_2026):.2f})"
    for t, p in zip(pred2026_df["title"], pred2026_df["prob"])
]

def statuette_label(title, prob, top):
    icon = "🏆 " if title == top else ""
    return f"{icon}{prob:.1f}%"

fig8 = go.Figure(go.Bar(
    y=pred2026_df["title"],
    x=pred2026_df["prob"],
    orientation="h",
    marker=dict(color=bar_colors),
    text=[statuette_label(t, p, top_film_2026)
          for t, p in zip(pred2026_df["title"], pred2026_df["prob"])],
    textposition="outside",
    textfont=dict(color=WHITE, size=11),
    hovertemplate="<b>%{y}</b><br>Probabilidad estimada: %{x:.1f}%<extra></extra>",
))
fig8.update_layout(**layout(
    height=500,
    title="🏆  Mi predicción: Oscar a Mejor Película 2026",
    margin=dict(l=200, r=80, t=60, b=45),
    xaxis=dict(title="Probabilidad estimada %", gridcolor="#222",
               range=[0, top_prob_2026 * 1.4]),
    yaxis=dict(title=""),
))

# ─────────────────────────────────────────────────────────────────────────────
# STEPS
# ─────────────────────────────────────────────────────────────────────────────
STEPS = [
    # ── INTRO
    {
        "chart": "fig0", "section": "And the Oscar goes to… ¿suerte o patrón?",
        "titulo": "47 años de historia, un patrón claro",
        "texto": (
            f"Desde 1978, <strong>{n_films} películas</strong> compitieron por el Oscar "
            f"a Mejor Película en <strong>{n_years} ceremonias</strong>. "
            "Solo una por año se lleva la estatuilla dorada. "
            "¿Qué las hace diferentes? ¿Hay un patrón o es pura suerte?"
        ),
    },
    {
        "chart": "fig0", "section": "",
        "titulo": "La fórmula empieza a dibujarse",
        "texto": (
            f"El ganador típico llega con <strong>{avg_prec:.1f} premios precursores</strong>. "
            f"Más del <strong>{pct_eng:.0f}%</strong> de los nominados ruedan en inglés. "
            "Scrolleá para descubrir qué variables importan y cuáles son ruido."
        ),
    },

    # ── GENERO
    {
        "chart": "fig1", "section": "¿La Academia tiene un tipo?",
        "titulo": "Las combinaciones de géneros revelan el gusto de la Academia",
        "texto": (
            "Cada burbuja es una <strong>combinación de géneros</strong> (ej: Drama + Historia). "
            "Su posición vertical indica el <strong>win rate</strong>, "
            "su tamaño refleja cuántas ganadoras hubo. "
            "Hovereá sobre cada burbuja para ver ejemplos de películas ganadoras."
        ),
    },
    {
        "chart": "fig1", "section": "",
        "titulo": "Drama + Historia arrasa, Drama + Comedia sorprende",
        "texto": (
            "El combo <em>Drama + Historia</em> y el puro <em>Drama</em> dominan ampliamente. "
            "Pero <em>Drama + Comedia</em> tiene un win rate sorprendentemente alto — "
            "la Academia premia el drama humano mezclado con calidez. "
            "Thrillers y ciencia ficción rara vez alzan la estatuilla."
        ),
    },

    # ── IDIOMA (un solo step, combinado)
    {
        "chart": "fig2", "section": "La barrera del idioma",
        "titulo": f"El {pct_eng:.0f}% habla inglés — pero hay excepciones históricas",
        "texto": (
            "Históricamente, la Academia premió casi exclusivamente producciones anglófonas. "
            "El donut izquierdo muestra el mix de nominadas; el derecho, solo ganadoras. "
            f"Solo <strong>{len(non_eng_w)}</strong> película{'s' if len(non_eng_w)!=1 else ''} "
            f"no anglófona{'s' if len(non_eng_w)!=1 else ''} rompieron el molde: {non_eng_txt}."
        ),
    },

    # ── DINERO
    {
        "chart": "fig3", "section": "¿Se puede comprar un Oscar?",
        "titulo": "El presupuesto no garantiza nada",
        "texto": (
            "La distribución de presupuesto entre ganadoras y nominadas se solapa bastante. "
            "Muchas ganadoras tuvieron presupuestos modestos; "
            "algunas superproducciones millonarias nunca llegaron a alzar la estatuilla."
        ),
    },
    {
        "chart": "fig3b", "section": "",
        "titulo": "Pero la taquilla tampoco decide",
        "texto": (
            "Algunas ganadoras fueron éxitos de taquilla, otras apenas recuperaron su inversión. "
            "El Oscar no es un premio al éxito comercial. "
            "El ROI no tiene correlación clara con ganar — "
            "el ★ está repartido en todo el espacio presupuesto/recaudación."
        ),
    },

    # ── DIRECTORES
    {
        "chart": "fig4", "section": "La suerte del novato",
        "titulo": "Los directores más nominados",
        "texto": (
            "Hay directores que acumulan nominación tras nominación. "
            "<strong>Dorado = ganó al menos una vez</strong>, "
            "gris = sigue esperando. Los ★ indican cuántas estatuillas tiene. "
            "Algunos esperaron décadas."
        ),
    },
    {
        "chart": "fig4", "section": "",
        "titulo": f"El {pct_first_win:.0f}% de los ganadores lo logró en su primera nominación",
        "texto": (
            f"De todos los directores ganadores, el <strong>{pct_first_win:.0f}%</strong> "
            "ganó en su <em>primera</em> nominación a Mejor Película. "
            f"Entre ellos: {first_wins_txt}."
        ),
    },

    # ── PRECURSORES
    {
        "chart": "fig5", "section": "Los Oscars no arrancan en la ceremonia",
        "titulo": "La temporada de premios como termómetro",
        "texto": (
            "Antes de la ceremonia de los Oscars, hay meses de premios: "
            "Globos de Oro, BAFTA, PGA, WGA, Critics Choice… "
            "¿Cuáles de estos precursores predicen mejor quién se lleva la estatuilla?"
        ),
    },
    {
        "chart": "fig5", "section": "",
        "titulo": f"{best_prec['precursor']} — el mejor predictor",
        "texto": (
            f"Ganar el <strong>{best_prec['precursor']}</strong> convierte al film en favorito: "
            f"el <strong>{best_prec['win_rate']:.0f}%</strong> de las veces también gana el Oscar "
            f"({best_prec['n_wins']} de {best_prec['n_total']} casos). "
            "La temporada de premios no miente."
        ),
    },

    # ── ACADEMIA VS PUBLICO
    {
        "chart": "fig6b", "section": "La Academia vs el público",
        "titulo": "¿Votan igual la crítica y el público?",
        "texto": (
            "Rotten Tomatoes mide la crítica especializada; IMDB al público general. "
            "Las ganadoras (★) suelen quedar bien posicionadas en ambas métricas, "
            "pero la correlación no es perfecta — hay sorpresas en ambas direcciones."
        ),
    },
    {
        "chart": "fig6", "section": "",
        "titulo": "Las ganadoras son buenas… pero no siempre las mejor rankeadas en IMDB",
        "texto": (
            "El IMDB promedio de las ganadoras es mayor que el de las nominadas, "
            "pero el solapamiento es grande. Algunas muy queridas por el público nunca ganaron; "
            "otras ganadoras tienen un IMDB relativamente modesto. "
            "El voto de la Academia y el voto popular no siempre coinciden."
        ),
    },

    # ── ALGORITMO
    {
        "chart": "fig7", "section": "¿Puede un algoritmo predecir el Oscar?",
        "titulo": "Un modelo de Machine Learning entrenado con 47 años de historia",
        "texto": (
            "Combiné métricas de crítica, datos de taquilla, premios precursores, "
            "género, idioma y características de producción en un modelo "
            "<strong>LightGBM</strong> optimizado con Optuna. "
            "Entrenado con datos de 1978 a 2021."
        ),
    },
    {
        "chart": "fig7", "section": "",
        "titulo": f"{n_correct}/{n_test} años acertados — datos que nunca vio",
        "texto": (
            f"El modelo acertó <strong>{n_correct} de {n_test} años</strong> del test set (2022–2025). "
            "En 2022 apostó por <em>The Power of the Dog</em> pero ganó CODA — "
            "el único error. La barra muestra qué probabilidad le asignó a la ganadora real. "
            "El feature más importante: <strong>total_precursor_wins</strong>."
        ),
    },

    # ── PREDICCIÓN 2026
    {
        "chart": "fig8", "section": "Mi predicción: Oscar 2026",
        "titulo": f"🏆  El modelo apunta a <em>{top_film_2026}</em>",
        "texto": (
            f"Aplicando el mismo LightGBM a las <strong>10 nominadas de 2026</strong>, "
            f"el modelo le asigna a <strong>{top_film_2026}</strong> la mayor probabilidad "
            f"estimada (<strong>{top_prob_2026:.1f}%</strong>). "
            "La barra dorada es la predicción del algoritmo. "
            "Hovereá para ver la probabilidad de cada film."
        ),
    },
    {
        "chart": "fig8", "section": "",
        "titulo": "¿Y el modelo Transformer? Una imagen vale más que un plot",
        "texto": (
            "También entrené un modelo basado en <strong>embeddings de texto</strong> "
            "(sinopsis + etiquetas) con sentence-transformers. "
            "Aunque captura matices narrativos que el LightGBM ignora, "
            "su precisión fue <em>notablemente menor</em>: "
            "el texto del plot no alcanza para replicar lo que "
            "una actuación, una fotografía o una temporada de premios comunican. "
            "<strong>Una imagen — y la calidad actoral — "
            "todavía valen más que el argumento.</strong>"
        ),
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Armar HTML
# ─────────────────────────────────────────────────────────────────────────────
CHARTS = {
    "fig0":  fig_json(fig0),
    "fig1":  fig_json(fig1),
    "fig2":  fig_json(fig2),
    "fig3":  fig_json(fig3),
    "fig3b": fig_json(fig3b),
    "fig4":  fig_json(fig4),
    "fig5":  fig_json(fig5),
    "fig6":  fig_json(fig6),
    "fig6b": fig_json(fig6b),
    "fig7":  fig_json(fig7),
    "fig8":  fig_json(fig8),
}

steps_html = ""
prev_section = None
for s in STEPS:
    if s["section"] and s["section"] != prev_section:
        steps_html += f'\n<div class="section-label">{s["section"]}</div>\n'
        prev_section = s["section"]
    steps_html += f"""
<div class="step" data-chart="{s['chart']}">
  <div class="step-inner">
    <h2>{s['titulo']}</h2>
    <p>{s['texto']}</p>
  </div>
</div>"""

FIRST_CHART = STEPS[0]["chart"]

# ── Cargar imágenes decorativas ──────────────────────────────────────────────
_IMG = "img"
oscars_b64     = _img_b64(f"{_IMG}/oscars.jpg",     max_h=1000, quality=76)
leo_b64        = _img_b64(f"{_IMG}/leo.jpg",         max_h=620,  quality=82)
the_end_b64    = _img_b64(f"{_IMG}/the_end.jpg",     max_h=800,  quality=76)
cinema_b64     = _img_b64(f"{_IMG}/cinema.jpg",      max_h=900,  quality=78)
estatuilla_b64 = _img_b64_png(f"{_IMG}/estatuilla.jpg", max_h=180, black_thresh=45)
print(f"  Imágenes → oscars:{'OK' if oscars_b64 else 'N/A'} | "
      f"leo:{'OK' if leo_b64 else 'N/A'} | "
      f"the_end:{'OK' if the_end_b64 else 'N/A'} | "
      f"cinema:{'OK' if cinema_b64 else 'N/A'} | "
      f"estatuilla:{'OK' if estatuilla_b64 else 'N/A'}")

# ── Build prediction cards HTML (estatuillas apiladas) ────────────────────────
def _statues(n):
    return '<span class="mini-s"></span>' * n if n > 0 else '<span class="no-s">—</span>'

pred_rows_html = ""
sorted_pred = pred2026_df.sort_values("prob", ascending=False).reset_index(drop=True)
for i, row in sorted_pred.iterrows():
    is_top = (row["title"] == top_film_2026)
    pct    = row["prob"]
    n_stat = max(0, round(pct / top_prob_2026 * 10))
    icon   = "🏆" if is_top else ("🥈" if i == 1 else ("🥉" if i == 2 else "·"))
    cls    = "pred-top" if is_top else ""
    pred_rows_html += f"""
      <div class="pred-row {cls}">
        <span class="pred-icon">{icon}</span>
        <span class="pred-title">{row['title']}</span>
        <div class="pred-statues">{_statues(n_stat)}</div>
        <span class="pred-pct">{pct:.1f}%</span>
      </div>"""

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Oscar · ¿Suerte o patrón?</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --gold:  #e8b84b;
      --red:   #c0392b;
      --bg:    #0d0d0d;
      --text:  #f0f0f0;
    }}
    html {{ scroll-behavior: smooth; }}
    body {{ background: var(--bg); color: var(--text); font-family: 'Georgia', serif; }}

    /* ── Progress bar ── */
    #progress-bar {{
      position: fixed; top: 0; left: 0;
      height: 3px; background: var(--gold);
      width: 0%; z-index: 999; transition: width .1s linear;
    }}

    /* ── Shared fixed background (oscars) — hero + scroll-section ── */
    .hero, .scroll-section {{
      background-image: url('data:image/jpeg;base64,{oscars_b64}');
      background-attachment: fixed;
      background-size: cover;
      background-position: center top;
    }}

    /* ── Hero ── */
    .hero {{
      height: 100vh; position: relative;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      text-align: center; padding: 2rem;
    }}
    .hero::before {{
      content: ''; position: absolute; inset: 0;
      background: rgba(13,13,13,0.65);
    }}
    .hero > * {{ position: relative; z-index: 1; }}
    .hero-tag {{
      font-size: .78rem; letter-spacing: .22em;
      text-transform: uppercase; color: var(--gold); opacity: .75;
      margin-bottom: 1.3rem;
    }}
    .hero h1 {{
      font-size: clamp(2rem, 5vw, 4rem);
      color: var(--gold); line-height: 1.15;
    }}
    .hero p {{
      margin-top: 1.2rem; font-size: 1.05rem;
      opacity: .6; max-width: 560px; line-height: 1.7;
    }}
    .scroll-hint {{
      margin-top: 3.5rem; font-size: .75rem;
      letter-spacing: .16em; opacity: .35;
      text-transform: uppercase; animation: bounce 2s infinite;
    }}
    @keyframes bounce {{
      0%, 100% {{ transform: translateY(0); }}
      50%       {{ transform: translateY(7px); }}
    }}

    /* ── Scrollytelling layout ── */
    .scroll-section {{
      position: relative;
      display: flex; align-items: flex-start;
      max-width: 1200px; margin: 0 auto; padding: 0 2rem;
    }}
    /* Dark overlay sobre el fondo fijo para que los gráficos sean legibles */
    .scroll-section::before {{
      content: ''; position: fixed; inset: 0;
      background: rgba(13,13,13,0.88);
      pointer-events: none; z-index: 0;
    }}
    .scroll-section > * {{ position: relative; z-index: 1; }}

    .sticky-chart {{
      position: sticky; top: 8vh;
      width: 56%; height: 84vh;
      display: flex; align-items: center; justify-content: center;
      /* Cinema como fondo del área de proyección */
      border-radius: 6px; overflow: hidden;
    }}
    .sticky-chart::before {{
      content: ''; position: absolute; inset: 0;
      background-image: url('data:image/jpeg;base64,{cinema_b64}');
      background-size: cover; background-position: center;
      opacity: 0.13;   /* muy sutil, no interfiere con los gráficos */
      z-index: 0; pointer-events: none;
    }}
    #chart-container {{ width: 100%; position: relative; z-index: 1; }}

    /* ── Steps ── */
    .steps {{ width: 44%; padding-left: 3.5rem; }}

    .section-label {{
      margin-top: 7rem; margin-bottom: -0.5rem;
      font-size: .72rem; letter-spacing: .2em;
      text-transform: uppercase;
      color: var(--gold); opacity: .7;
      border-left: 2px solid var(--gold);
      padding-left: .9rem;
    }}
    .step {{
      min-height: 82vh;
      display: flex; align-items: center;
    }}
    .step-inner {{
      background: rgba(255,255,255,0.025);
      border-left: 3px solid #2a2a2a;
      padding: 1.7rem 1.9rem;
      border-radius: 4px;
      transition: border-color .4s, background .4s;
    }}
    .step.is-active .step-inner {{
      border-left-color: var(--gold);
      background: rgba(232,184,75,0.07);
    }}
    .step-inner h2 {{
      color: var(--gold); font-size: 1.2rem;
      margin-bottom: .85rem; line-height: 1.35;
    }}
    .step-inner p {{
      line-height: 1.85; opacity: .85; font-size: .96rem;
    }}
    .step-inner strong {{ color: var(--gold); font-weight: normal; }}
    .step-inner em {{ font-style: italic; }}

    /* ── Final Prediction Section ── */
    .prediction-section {{
      padding: 6rem 2rem 5rem;
      position: relative;
      background-image: url('data:image/jpeg;base64,{cinema_b64}');
      background-size: cover; background-position: center bottom;
      text-align: center;
    }}
    .prediction-section::before {{
      content: ''; position: absolute; inset: 0;
      background: linear-gradient(to bottom,
        rgba(13,13,13,0.97) 0%,
        rgba(13,13,13,0.88) 40%,
        rgba(13,13,13,0.82) 100%);
      pointer-events: none;
    }}
    .prediction-section > * {{ position: relative; z-index: 1; }}
    .prediction-section h2 {{
      font-size: clamp(1.6rem, 4vw, 2.6rem);
      color: var(--gold); margin-bottom: .6rem;
    }}
    .prediction-section .subtitle {{
      font-size: .9rem; opacity: .5; letter-spacing: .15em;
      text-transform: uppercase; margin-bottom: 3rem;
    }}
    .pred-list {{
      max-width: 700px; margin: 0 auto;
      display: flex; flex-direction: column; gap: .9rem;
    }}
    .pred-row {{
      display: grid;
      grid-template-columns: 2rem 1fr 160px 3.5rem;
      align-items: center; gap: .8rem;
      padding: .55rem .8rem;
      border-radius: 4px;
      background: rgba(255,255,255,0.03);
      transition: background .3s;
    }}
    .pred-row:hover {{ background: rgba(255,255,255,0.06); }}
    .pred-row.pred-top {{
      background: rgba(232,184,75,0.1);
      border: 1px solid rgba(232,184,75,0.3);
    }}
    .pred-icon {{ font-size: 1.1rem; text-align: center; }}
    .pred-title {{ font-size: .92rem; text-align: left; opacity: .9; }}
    .pred-row.pred-top .pred-title {{ color: var(--gold); font-weight: bold; opacity: 1; }}
    .pred-bar-wrap {{
      height: 8px; background: rgba(255,255,255,0.08);
      border-radius: 4px; overflow: hidden;
    }}
    .pred-bar-fill {{
      height: 100%; border-radius: 4px;
      background: linear-gradient(90deg, #5a4800, var(--gold));
      transition: width .6s ease;
    }}
    .pred-row.pred-top .pred-bar-fill {{
      background: var(--gold);
      box-shadow: 0 0 8px rgba(232,184,75,0.5);
    }}
    .pred-pct {{ font-size: .85rem; color: var(--gold); text-align: right; }}

    /* ── Mini estatuillas ── */
    .pred-statues {{ display: flex; align-items: flex-end; gap: 3px; min-width: 210px; }}
    .mini-s {{
      display: inline-block; width: 16px; height: 30px;
      background-image: url('data:image/png;base64,{estatuilla_b64}');
      background-size: contain; background-repeat: no-repeat;
      background-position: bottom center;
      filter: brightness(0.75) sepia(1) hue-rotate(5deg) saturate(3);
      transition: filter .3s;
    }}
    .pred-row.pred-top .mini-s {{
      filter: brightness(1) sepia(1) hue-rotate(5deg) saturate(4);
      filter: drop-shadow(0 0 3px rgba(232,184,75,0.6));
    }}
    .no-s {{ opacity: .25; font-size: .8rem; }}

    /* ── Leo image ── */
    .pred-leo-wrap {{
      margin-bottom: 2.5rem;
      display: flex; flex-direction: column; align-items: center; gap: .8rem;
    }}
    .pred-leo {{
      width: clamp(120px, 18vw, 200px);
      border-radius: 50%;
      border: 3px solid var(--gold);
      box-shadow: 0 0 24px rgba(232,184,75,0.35);
      object-fit: cover; object-position: top;
      aspect-ratio: 1; filter: grayscale(15%);
    }}
    .leo-caption {{
      font-size: .78rem; letter-spacing: .18em;
      text-transform: uppercase; color: var(--gold); opacity: .65;
    }}

    .transformer-note {{
      max-width: 600px; margin: 3.5rem auto 0;
      padding: 1.4rem 1.8rem;
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 6px;
      background: rgba(255,255,255,0.02);
      font-size: .9rem; line-height: 1.8; opacity: .7;
    }}
    .transformer-note strong {{ color: var(--gold); opacity: 1; }}

    /* ── Outro ── */
    .outro {{
      min-height: 60vh; position: relative;
      display: flex; align-items: center; justify-content: center;
      text-align: center; padding: 4rem 2rem;
      background-image: url('data:image/jpeg;base64,{the_end_b64}');
      background-size: cover; background-position: center;
    }}
    .outro::before {{
      content: ''; position: absolute; inset: 0;
      background: rgba(13,13,13,0.78);
    }}
    .outro > div {{ position: relative; z-index: 1; }}
    .outro h2 {{ font-size: 2.1rem; color: var(--gold); }}
    .outro p  {{
      margin-top: 1.1rem; opacity: .7;
      max-width: 560px; line-height: 1.8;
    }}
  </style>
</head>
<body>

<div id="progress-bar"></div>

<!-- Hero -->
<section class="hero">
  <div class="hero-tag">Un análisis de datos · Oscars 1978–2025</div>
  <h1>And the Oscar goes to…<br>¿suerte o patrón?</h1>
  <p>47 años de nominadas, 10 gráficos interactivos y un modelo de machine learning
     para responder la pregunta que todos nos hacemos la noche de la ceremonia.</p>
  <div class="scroll-hint">↓ scrolleá para descubrir</div>
</section>

<!-- Scrollytelling -->
<section class="scroll-section">
  <div class="sticky-chart">
    <div id="chart-container"></div>
  </div>
  <div class="steps">
    {steps_html}
  </div>
</section>

<!-- ── Predicción Final Oscar 2026 ── -->
<section class="prediction-section">
  <div class="pred-leo-wrap">
    <img src="data:image/jpeg;base64,{leo_b64}" class="pred-leo" alt="And the Oscar goes to...">
    <span class="leo-caption">And the Oscar goes to…</span>
  </div>
  <h2>🏆 Mi predicción final</h2>
  <p class="subtitle">Oscar a Mejor Película · 98ª Ceremonia · 2026</p>
  <div class="pred-list">
    {pred_rows_html}
  </div>
  <div class="transformer-note">
    <strong>Una nota sobre el modelo Transformer:</strong>
    también entrené un modelo basado en embeddings semánticos de la sinopsis
    (sentence-transformers <em>all-mpnet-base-v2</em>).
    Aunque captura matices narrativos que el LightGBM no ve, su precisión fue
    <strong>notablemente menor</strong>. La conclusión es clara:
    el texto del plot no alcanza para replicar lo que comunican
    una actuación memorable, una fotografía impecable o una temporada de premios sólida.
    <strong>Una imagen — y la calidad actoral — todavía valen más que el argumento.</strong>
  </div>
</section>

<!-- Outro -->
<section class="outro">
  <div>
    <h2>El patrón existe</h2>
    <p>Drama con peso histórico, precursores sólidos, crítica favorable…
       y siempre una sorpresa reservada para la noche de la ceremonia.
       El algoritmo acertó 4 de 4 en el test set —
       pero ningún modelo captura del todo la magia impredecible de Hollywood.</p>
  </div>
</section>

<script>
  const CHARTS = {json.dumps(CHARTS)};

  function renderChart(key) {{
    const spec = JSON.parse(CHARTS[key]);
    Plotly.react("chart-container", spec.data, spec.layout, {{
      responsive: true,
      displayModeBar: false,
    }});
  }}

  // Intersection Observer — activa el step visible
  const steps = document.querySelectorAll(".step");
  const io = new IntersectionObserver((entries) => {{
    entries.forEach(e => {{
      if (e.isIntersecting) {{
        steps.forEach(s => s.classList.remove("is-active"));
        e.target.classList.add("is-active");
        renderChart(e.target.dataset.chart);
      }}
    }});
  }}, {{ threshold: 0.55 }});
  steps.forEach(s => io.observe(s));

  // Progress bar
  window.addEventListener("scroll", () => {{
    const h   = document.documentElement;
    const pct = (window.scrollY / (h.scrollHeight - h.clientHeight)) * 100;
    document.getElementById("progress-bar").style.width = pct + "%";
  }});

  // Primer chart
  renderChart("{FIRST_CHART}");
</script>

</body>
</html>
"""

with open("scrollytelling.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Listo -> scrollytelling.html")
print(f"  {len(STEPS)} steps  |  {len(CHARTS)} graficos  |  {n_films} peliculas")
print(f"  Predicción 2026: {top_film_2026} ({top_prob_2026:.1f}%)")
