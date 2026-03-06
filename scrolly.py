"""
genera_scrollytelling.py
Corre: python genera_scrollytelling.py
Abre:  scrollytelling.html
"""

import json
import pandas as pd
import plotly.graph_objects as go

# ── Datos ──────────────────────────────────────────────────────────────────
df = pd.read_csv("data/master_dataset.csv")

# ── Helpers ────────────────────────────────────────────────────────────────

def fig_to_json(fig):
    return fig.to_json()


# ── Gráfico 1: wins por año ────────────────────────────────────────────────
wins_by_year = (
    df[df["won_best_picture"] == 1]
    .groupby("ceremony_year")[["total_precursor_wins", "critic_composite"]]
    .first()
    .reset_index()
)

fig1 = go.Figure(go.Bar(
    x=wins_by_year["ceremony_year"],
    y=wins_by_year["total_precursor_wins"],
    marker_color="#e8b84b",
    text=wins_by_year["total_precursor_wins"],
    textposition="outside",
))
fig1.update_layout(
    title="Precursor wins del ganador (por año)",
    xaxis_title="Año", yaxis_title="Wins",
    plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d",
    font_color="white", height=420,
)

# ── Gráfico 2: scatter critic composite vs precursor wins ──────────────────
winners = df[df["won_best_picture"] == 1]
losers  = df[df["won_best_picture"] == 0]

fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=losers["critic_composite"], y=losers["total_precursor_wins"],
    mode="markers", name="Nominadas",
    marker=dict(color="#555", size=6, opacity=0.5),
    text=losers["nominated_title"],
))
fig2.add_trace(go.Scatter(
    x=winners["critic_composite"], y=winners["total_precursor_wins"],
    mode="markers", name="Ganadoras",
    marker=dict(color="#e8b84b", size=10, symbol="star"),
    text=winners["nominated_title"],
))
fig2.update_layout(
    title="Crítica vs Precursores",
    xaxis_title="Critic composite", yaxis_title="Precursor wins",
    plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d",
    font_color="white", height=420,
)

# ── Gráfico 3: main_genre de ganadoras ────────────────────────────────────
genre_counts = (
    df[df["won_best_picture"] == 1]["main_genre"]
    .value_counts()
    .reset_index()
)
fig3 = go.Figure(go.Bar(
    x=genre_counts["main_genre"],
    y=genre_counts["count"],
    marker_color="#e8b84b",
))
fig3.update_layout(
    title="Género más frecuente en ganadoras",
    xaxis_title="Género", yaxis_title="Cantidad",
    plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d",
    font_color="white", height=420,
)

# ── Steps del scrollytelling ───────────────────────────────────────────────
STEPS = [
    {
        "chart": "fig1",
        "titulo": "¿Los precursores predicen el Oscar?",
        "texto": (
            "Cada barra es el ganador del año. "
            "Los films que llegan con más victorias en BAFTA, "
            "Globos de Oro y PGA casi siempre se llevan la estatuilla."
        ),
    },
    {
        "chart": "fig2",
        "titulo": "Crítica y premios van de la mano",
        "texto": (
            "Las ganadoras (★) se concentran en la esquina "
            "superior derecha: alta crítica <em>y</em> muchos precursores. "
            "Muy pocas ganaron con baja puntuación crítica."
        ),
    },
    {
        "chart": "fig3",
        "titulo": "El Drama domina",
        "texto": (
            "Casi el 90 % de las ganadoras son Dramas. "
            "Comedy y Adventure aparecen de vez en cuando, "
            "pero la Academia tiene un gusto muy marcado."
        ),
    },
]

# ── Template HTML ──────────────────────────────────────────────────────────
CHARTS = {
    "fig1": fig_to_json(fig1),
    "fig2": fig_to_json(fig2),
    "fig3": fig_to_json(fig3),
}

steps_html = ""
for i, s in enumerate(STEPS):
    steps_html += f"""
    <div class="step" data-chart="{s['chart']}">
      <div class="step-inner">
        <h2>{s['titulo']}</h2>
        <p>{s['texto']}</p>
      </div>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Oscar Scrollytelling</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: #0d0d0d;
      color: #f0f0f0;
      font-family: 'Georgia', serif;
    }}

    /* ── Hero ── */
    .hero {{
      height: 100vh;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      text-align: center; padding: 2rem;
    }}
    .hero h1 {{ font-size: clamp(2rem, 5vw, 4rem); color: #e8b84b; }}
    .hero p  {{ margin-top: 1rem; font-size: 1.2rem; opacity: .7; }}

    /* ── Layout sticky ── */
    .scroll-section {{
      display: flex;
      align-items: flex-start;
      max-width: 1100px;
      margin: 0 auto;
      padding: 0 1.5rem;
    }}

    .sticky-chart {{
      position: sticky;
      top: 10vh;
      width: 55%;
      height: 80vh;
      display: flex; align-items: center; justify-content: center;
    }}

    #chart-container {{
      width: 100%;
    }}

    /* ── Steps ── */
    .steps {{
      width: 45%;
      padding-left: 3rem;
    }}

    .step {{
      min-height: 80vh;
      display: flex; align-items: center;
    }}

    .step-inner {{
      background: rgba(255,255,255,0.04);
      border-left: 3px solid #e8b84b;
      padding: 1.5rem 1.5rem;
      border-radius: 4px;
      transition: background .3s;
    }}

    .step.is-active .step-inner {{
      background: rgba(232,184,75,0.08);
    }}

    .step-inner h2 {{
      color: #e8b84b;
      font-size: 1.3rem;
      margin-bottom: .75rem;
    }}

    .step-inner p {{
      line-height: 1.7;
      opacity: .85;
    }}

    /* ── Outro ── */
    .outro {{
      min-height: 60vh;
      display: flex; align-items: center; justify-content: center;
      text-align: center; padding: 3rem;
    }}
    .outro h2 {{ font-size: 2rem; color: #e8b84b; }}
    .outro p  {{ margin-top: 1rem; opacity: .7; max-width: 600px; }}
  </style>
</head>
<body>

<!-- Hero -->
<section class="hero">
  <h1>🏆 ¿Qué hace a una película ganar el Oscar?</h1>
  <p>Un análisis de las nominadas a Mejor Película desde 1978</p>
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

<!-- Outro -->
<section class="outro">
  <div>
    <h2>El patrón es claro</h2>
    <p>Drama + buena crítica + precursores = favorito. 
       Pero siempre hay una sorpresa.</p>
  </div>
</section>

<!-- Data + lógica -->
<script>
  const CHARTS = {json.dumps(CHARTS)};

  function renderChart(chartKey) {{
    const spec = JSON.parse(CHARTS[chartKey]);
    Plotly.react("chart-container", spec.data, spec.layout, {{responsive: true}});
  }}

  // Intersection Observer
  const steps = document.querySelectorAll(".step");

  const observer = new IntersectionObserver((entries) => {{
    entries.forEach(entry => {{
      if (entry.isIntersecting) {{
        steps.forEach(s => s.classList.remove("is-active"));
        entry.target.classList.add("is-active");
        renderChart(entry.target.dataset.chart);
      }}
    }});
  }}, {{ threshold: 0.5 }});

  steps.forEach(s => observer.observe(s));

  // Renderizar primer chart al cargar
  renderChart("{STEPS[0]['chart']}");
</script>

</body>
</html>
"""

with open("scrollytelling.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Listo -> scrollytelling.html")
