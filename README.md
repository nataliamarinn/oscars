# 🎬 ¿Puede un algoritmo predecir el Oscar a Mejor Película?

Un proyecto de ciencia de datos que analiza 47 años de historia de los Premios Oscar
para encontrar los patrones detrás de los ganadores a Mejor Película — y predecir 2026.

## 🔍 ¿Qué hay aquí?

- **Dataset propio**: 200+ películas nominadas (1978–2025) con métricas de crítica,
  taquilla, premios precursores, género, idioma y más
- **Modelo LightGBM** con optimización de hiperparámetros via Optuna y división
  temporal estricta (nunca datos del futuro)
- **Modelo NLP experimental** con LDA + Sentence Transformers (all-mpnet-base-v2)
- **Scrollytelling interactivo**: 10 visualizaciones Plotly embebidas en una narrativa web
- **Predicciones 2026** basadas en señales de precursores actualizadas

## 📊 Resultados

| Modelo | Accuracy (test 2016–2021) |
|--------|--------------------------|
| LightGBM + features percentiles | 3/4 ceremonias ✅ |
| Transformer NLP (texto) | 0/4 ceremonias ❌ |

El modelo tabular funciona. El de texto falla — y eso también es un resultado valioso.

## 🏆 Predicciones 2026 (98ª ceremonia)

| Película | Probabilidad |
|----------|-------------|
| One Battle After Another | 37.1% |
| Hamnet | 31.7% |
| Marty Supreme | 16.6% |

## 🛠️ Stack

