# PlotCraft

Gráficos científicos y estadística con una interfaz sencilla para Linux.
Flujo guiado (tabla → gráfico) con personalización profunda cuando la necesitas.

> Estado: **v0.5**. Proyecto independiente, no afiliado a GraphPad ni OriginLab.

## Qué hace
- Hojas de datos editables: **Ctrl+C / Ctrl+X / Ctrl+V / Supr**, menú *Editar* y clic derecho. Se pega donde está el cursor
  (también con fila de títulos) y se conservan las filas vacías. Las hojas de 1 factor y XY **agregan columnas solas**
  al escribir en la última, o desde el menú (insertar/eliminar columna). Doble clic en el encabezado para renombrar.
- Gráfico de barras con media ± SEM / SD / IC95 y puntos individuales opcionales.
- Etiquetas del eje X que se giran solas si no caben.
- Panel de propiedades: título, ejes, colores, fuente, tamaño, límites del eje Y.
- **Análisis estadístico** (pestaña *Análisis*): t de Student, t de Welch, t apareada y ANOVA de una vía.
- **Post hoc:** Tukey, Dunnett (vs. control), Bonferroni, Sidak, Holm-Sidak y Newman-Keuls, con IC cuando el método los define.
- **ANOVA de dos vías** (diseño *2 factores, formato largo*: columnas Factor A, Factor B, Valor): SC tipo III, interacción,
  % de variación, efectos simples con Tukey/Bonferroni/Sidak/Holm-Sidak y gráfico de barras agrupadas con asteriscos.
- **Pruebas no paramétricas:** Mann-Whitney, Wilcoxon (apareada), Kruskal-Wallis y Friedman, con post hoc de Dunn
  (Bonferroni, Holm o Sidak). Gráfico con *Mediana ± RIQ*.
- **Más tipos de gráfico** (selector *Gráfico* junto al diseño de datos):
  - 1 factor: barras, **cajas y bigotes** (1.5×RIQ o mín–máx, con puntos opcionales) e **histograma** (bins comunes, frecuencia o densidad).
  - 2 factores: barras agrupadas y **cajas agrupadas**.
  - **XY**: dispersión (con recta de tendencia y R²), líneas y puntos, líneas. Las filas con el mismo X se promedian
    (media ± SEM/SD/IC95 o mediana ± RIQ). Ejes X/Y logarítmicos.
  - **Burbujas 2D**: X, Y, tamaño (área proporcional) y grupo opcional, con leyenda de tamaños.
  - El panel derecho solo muestra las opciones del gráfico elegido.
- **Regresión dosis-respuesta 4PL (IC50)** en el diseño XY: ajuste por serie con todas las réplicas, Bottom/Top/Hill
  libres o fijos, EE e IC95% de cada parámetro, R², Sy.x y el IC50 con su intervalo. Gráfico *Dosis-respuesta (4PL)*
  con la curva, los puntos (media ± error) y guías del IC50. Convención de Prism (Hill negativa si la curva desciende).
- **Asteriscos sobre el gráfico** (`ns`, `*`, `**`, `***`, `****`), con corchetes que no se solapan. El análisis se recalcula solo al cambiar los datos.
- Exportar a PNG, SVG, PDF (300 dpi). Guardar/abrir proyectos `.pcft`.

## Instalación (Ubuntu)
```bash
sudo apt install python3-venv libxcb-cursor0
bash scripts/install.sh
```
El script crea el entorno virtual, instala PlotCraft y lo agrega al **menú de aplicaciones** (con ícono, y los archivos
`.pcft` se abren con doble clic). Búscalo como «PlotCraft»; la primera vez puede requerir cerrar sesión.

Manualmente, o para desarrollar:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
plotcraft                       # abre la aplicación (también: plotcraft proyecto.pcft)
plotcraft --install-launcher    # agrega el lanzador al menú
plotcraft --uninstall-launcher  # lo quita
pytest                          # tests
```
El lanzador usa el Python del entorno virtual: si mueves la carpeta, vuelve a ejecutar `plotcraft --install-launcher`.

## Estructura
```
src/plotcraft/core/   # lógica sin interfaz (estadística, gráficos, proyecto)
src/plotcraft/ui/     # interfaz PySide6
tests/                # pytest (core + prueba de humo de la UI)
```

## Hoja de ruta
- Pendiente: deshacer/rehacer, comparar curvas (IC50 entre series), otros modelos no lineales, correlación, ANOVA de medidas repetidas, Dunnett en 2 factores, comparaciones entre pares elegidos.
- v0.3: regresión no lineal 4PL (IC50), tablas XY y agrupadas.
- Después: supervivencia, procesamiento por lotes, Flatpak/AppImage.

Todo cálculo estadístico debe validarse contra R antes de publicarse.

## Licencia
MIT (puedes cambiarla a GPL-3 si prefieres que las derivadas sigan libres).

## Validación estadística
Los tests (`pytest`) comparan contra scipy y statsmodels: t y ANOVA (scipy), Tukey con IC (statsmodels),
Bonferroni/Sidak/Holm-Sidak (`multipletests`), ANOVA de dos vías tipo III (statsmodels, balanceado y desbalanceado), Dunn (scikit-posthocs). Dunnett usa `scipy.stats.dunnett` con semilla fija
(integración numérica, precisión ≈ 0.001). Newman-Keuls es una implementación propia verificada con
propiedades (coincide con Tukey en el rango completo y con 2 grupos, decisiones escalonadas coherentes);
**no se ha contrastado contra R/Prism**; lo mismo aplica a Friedman+Dunn: hazlo con tus datos antes de publicar.

**Ajuste 4PL:** se compara contra `lmfit` (parámetros, errores estándar, SSE, R²) y, por simulación, el IC95% del IC50
cubre el valor verdadero ≈ 94–95 % de las veces con ruido bajo y moderado (con mucho ruido los intervalos son
conservadores y la aplicación avisa cuando el IC50 está mal determinado). Los IC son asintóticos (Wald), no de
verosimilitud perfilada, y el IC50 es el *relativo* (a mitad de camino entre Bottom y Top); pueden diferir de los de Prism
cuando hay pocos puntos.
