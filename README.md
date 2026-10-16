# PlotCraft

Gráficos científicos y estadística con una interfaz sencilla para Linux.
Flujo guiado (tabla → gráfico) con personalización profunda cuando la necesitas.

> Estado: **v0.1 (MVP)**. Proyecto independiente, no afiliado a GraphPad ni OriginLab.

## Qué hace la v0.1
- Hoja de datos editable (pega desde Excel/LibreOffice con Ctrl+V; doble clic en el encabezado para renombrar).
- Gráfico de barras con media ± SEM / SD / IC95 y puntos individuales opcionales.
- Etiquetas del eje X que se giran solas si no caben.
- Panel de propiedades: título, ejes, colores, fuente, tamaño, límites del eje Y.
- Exportar a PNG, SVG, PDF (300 dpi). Guardar/abrir proyectos `.pcft`.

## Instalación (Ubuntu)
```bash
sudo apt install python3-venv libxcb-cursor0
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
plotcraft          # o: python -m plotcraft
pytest             # correr tests
```

## Estructura
```
src/plotcraft/core/   # lógica sin interfaz (estadística, gráficos, proyecto)
src/plotcraft/ui/     # interfaz PySide6
tests/                # pytest (core + prueba de humo de la UI)
```

## Hoja de ruta
- v0.2: t-test, ANOVA, post hoc (Tukey/Dunnett), asteriscos de significancia, deshacer/rehacer.
- v0.3: regresión no lineal 4PL (IC50), tablas XY y agrupadas.
- Después: supervivencia, procesamiento por lotes, Flatpak/AppImage.

Todo cálculo estadístico debe validarse contra R antes de publicarse.

## Licencia
MIT (puedes cambiarla a GPL-3 si prefieres que las derivadas sigan libres).
