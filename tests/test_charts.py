import math

import numpy as np
import pytest
from scipy import stats

from plotcraft.core.plots_box_hist import make_box_figure, make_grouped_box_figure, make_hist_figure
from plotcraft.core.plots_xy import bubble_areas, make_bubble_figure, make_xy_figure, trend_line
from plotcraft.core.plotting import make_bar_figure, make_grouped_figure
from plotcraft.core.project import Project
from plotcraft.core.style import CHARTS, OPTION_CHARTS, WHISKERS, PlotStyle
from plotcraft.core.twoway import TwoWayData
from plotcraft.core.xydata import BubbleData, XYData

DATA = {"A": [1.0, 2, 3, 4, 5, 6, 7, 8, 9, 40], "B": [10.0, 11, 12, 13, 14, 15, 16, 17, 18, 19]}


def td():
    t = TwoWayData("Trat", "Tiempo", "Viab")
    for a in ("C", "T"):
        for b in ("24h", "48h"):
            for v in (1.0, 2.0, 3.0, 4.0):
                t.a.append(a); t.b.append(b); t.y.append(v + (5 if a == "T" else 0) + (2 if b == "48h" else 0))
    return t


# ---------- regresión de colores / ejes ----------
def test_single_gray_palette_is_uniform_for_one_factor_but_distinct_for_legend():
    fig = make_bar_figure({"A": [1.0, 2], "B": [3.0, 4], "C": [5.0, 6]}, PlotStyle(palette="Gris"))
    faces = {tuple(p.get_facecolor()) for p in fig.axes[0].patches}
    assert len(faces) == 1
    fig = make_grouped_figure(td(), PlotStyle(palette="Gris"))
    assert len({tuple(p.get_facecolor()) for p in fig.axes[0].patches}) == 2


def test_default_ymin_is_auto_and_bars_start_at_zero():
    assert PlotStyle().ymin is None
    fig = make_bar_figure({"A": [50.0, 52, 51]}, PlotStyle())
    assert fig.axes[0].get_ylim()[0] == 0


# ---------- cajas ----------
def _whisker_limits(ax):
    ys = [l.get_ydata() for l in ax.lines if len(l.get_ydata()) == 2 and l.get_xdata()[0] == l.get_xdata()[1]]
    return min(min(y) for y in ys), max(max(y) for y in ys)


def test_box_plot_medians_and_whiskers():
    fig = make_box_figure(DATA, PlotStyle(whisker=WHISKERS[1]))
    ax = fig.axes[0]
    assert len(ax.patches) == 2
    medians = sorted(l.get_ydata()[0] for l in ax.lines if len(l.get_ydata()) == 2 and l.get_color() == "black"
                     and l.get_ydata()[0] == l.get_ydata()[1] and l.get_linewidth() > 1.5)
    assert medians == pytest.approx([np.median(DATA["A"]), np.median(DATA["B"])])
    assert _whisker_limits(ax)[1] == pytest.approx(40)           # mín-máx llega hasta el máximo
    fig2 = make_box_figure(DATA, PlotStyle(whisker=WHISKERS[0]))   # 1.5 RIQ: 40 es atípico
    assert _whisker_limits(fig2.axes[0])[1] < 40


def test_box_plot_brackets_and_points():
    fig = make_box_figure(DATA, PlotStyle(show_points=True), comparisons=[("A", "B", "**")])
    ax = fig.axes[0]
    assert [t.get_text() for t in ax.texts] == ["**"]
    assert sum(len(c.get_offsets()) for c in ax.collections) == 20
    top = max(max(l.get_ydata()) for l in ax.lines)
    assert top > 40                                                # el corchete queda por encima del máximo


def test_grouped_box():
    fig = make_grouped_box_figure(td(), PlotStyle(), comparisons=[(("C", "24h"), ("C", "48h"), "*")])
    ax = fig.axes[0]
    assert len(ax.patches) == 4 and [t.get_text() for t in ax.texts] == ["*"]
    assert ax.get_legend().get_title().get_text() == "Tiempo"


# ---------- histograma ----------
def test_histogram_shared_bins_and_density():
    rng = np.random.default_rng(0)
    d = {"A": list(rng.normal(0, 1, 300)), "B": list(rng.normal(3, 1, 300))}
    fig = make_hist_figure(d, PlotStyle(bins=12, density=True))
    ax = fig.axes[0]
    assert len(ax.patches) == 24
    widths = {round(p.get_width(), 9) for p in ax.patches}
    assert len(widths) == 1                                        # mismos intervalos para ambos grupos
    area = sum(p.get_height() * p.get_width() for p in ax.patches[:12])
    assert area == pytest.approx(1.0)
    assert ax.get_ylabel() == "Densidad"
    freq = make_hist_figure(d, PlotStyle(bins=12)).axes[0]
    assert sum(p.get_height() for p in freq.patches[:12]) == 300 and freq.get_ylabel() == "Frecuencia"


# ---------- XY ----------
XY = XYData("Dosis", [1.0, 1, 2, 2, 3, 3, 4, 4], {"A": [1.0, 1.2, 2, 2.2, 3, 3.1, 4, 4.3],
                                                    "B": [2.0, 2.0, 4, 4, 6, 6, 8, 8]})


def test_scatter_shows_every_point_and_trendline_matches_scipy():
    fig = make_xy_figure(XY, PlotStyle(trendline=True), kind="Dispersión")
    ax = fig.axes[0]
    assert [len(c.get_offsets()) for c in ax.collections] == [8, 8]
    pts = XY.points("A")
    ref = stats.linregress([p[0] for p in pts], [p[1] for p in pts])
    slope, icpt, r2 = trend_line([p[0] for p in pts], [p[1] for p in pts])
    assert (slope, icpt, r2) == pytest.approx((ref.slope, ref.intercept, ref.rvalue ** 2))
    labels = [l.get_label() for l in ax.lines]
    assert any(f"R² = {r2:.3f}" in lab for lab in labels)
    line = [l for l in ax.lines if l.get_linestyle() == "--"][0]
    assert line.get_ydata()[0] == pytest.approx(icpt + slope * 1.0)


def test_lines_average_replicates_with_error():
    fig = make_xy_figure(XY, PlotStyle(error_type="SD"), kind="Líneas y puntos")
    ax = fig.axes[0]
    main = [l for l in ax.lines if len(l.get_xdata()) == 4][0]       # 4 X únicos
    assert list(main.get_xdata()) == [1, 2, 3, 4]
    assert list(main.get_ydata()) == pytest.approx([1.1, 2.1, 3.05, 4.15])
    assert len(ax.containers) == 2                                    # barras de error por serie
    raw = make_xy_figure(XY, PlotStyle(average_reps=False), kind="Líneas")
    assert max(len(l.get_xdata()) for l in raw.axes[0].lines) == 8


def test_xy_log_axes_labels_and_empty():
    fig = make_xy_figure(XY, PlotStyle(x_log=True, y_log=True), kind="Líneas")
    assert fig.axes[0].get_xscale() == "log" and fig.axes[0].get_yscale() == "log"
    assert fig.axes[0].get_xlabel() == "Dosis"
    assert make_xy_figure(XYData(), PlotStyle()) is not None


# ---------- burbujas ----------
def test_bubble_area_is_proportional_to_size():
    bd = BubbleData("x", "y", "Dosis", "Línea", [1.0, 2, 3], [1.0, 2, 3], [10.0, 20.0, 40.0], ["a", "a", "b"])
    fig = make_bubble_figure(bd, PlotStyle())
    ax = fig.axes[0]
    areas = np.concatenate([c.get_sizes() for c in ax.collections if len(c.get_offsets())])
    assert areas[1] / areas[0] == pytest.approx(2.0) and areas[2] / areas[0] == pytest.approx(4.0)
    assert bubble_areas([10, 40], 2.0)[1] == pytest.approx(2 * bubble_areas([10, 40], 1.0)[1])
    texts = [t.get_text() for leg in fig.axes[0].get_children() if leg.__class__.__name__ == "Legend"
             for t in leg.get_texts()]
    assert {"a", "b", "10", "40"} <= set(texts)


def test_bubble_ignores_nonpositive_and_missing():
    bd = BubbleData(x=[1.0, 2, 3, 4], y=[1.0, 2, 3, math.nan], size=[5.0, -1.0, 0.0, 3.0], group=["", "", "", ""])
    fig = make_bubble_figure(bd, PlotStyle())
    assert sum(len(c.get_offsets()) for c in fig.axes[0].collections) == 1
    assert make_bubble_figure(BubbleData(), PlotStyle()) is not None


# ---------- datos / proyecto / catálogo ----------
def test_xydata_and_project_roundtrip(tmp_path):
    xy = XYData("D", [1.0, 2.0], {"A": [1.0, math.nan], "B": [3.0, 4.0]})
    p = Project("t", mode="xy", xy=xy, bubble=BubbleData("a", "b", "s", "g", [1.0], [2.0], [3.0], ["k"]),
                style=PlotStyle(chart="Líneas y puntos", bins=7, trendline=True))
    f = tmp_path / "x.pcft"
    p.save(f)
    q = Project.load(f)
    assert q.mode == "xy" and math.isnan(q.xy.series["A"][1]) and q.xy.series["B"] == [3.0, 4.0]
    assert q.bubble.group == ["k"] and q.style.chart == "Líneas y puntos" and q.style.bins == 7


def test_chart_catalog_is_consistent():
    all_charts = {c for v in CHARTS.values() for c in v}
    assert all(set(v) <= all_charts for v in OPTION_CHARTS.values())
    assert CHARTS["xy"] == ("Dispersión", "Líneas y puntos", "Líneas", "Dosis-respuesta (4PL)")


def test_axis_labels_are_automatic_by_default():
    assert PlotStyle().xlabel == "" and PlotStyle().ylabel == ""
    assert make_bar_figure(DATA, PlotStyle()).axes[0].get_xlabel() == "Grupo"
    assert make_box_figure(DATA, PlotStyle()).axes[0].get_ylabel() == "Valor"
    assert make_grouped_figure(td(), PlotStyle()).axes[0].get_xlabel() == "Trat"
    assert make_xy_figure(XY, PlotStyle(), kind="Líneas").axes[0].get_xlabel() == "Dosis"
    assert make_bar_figure(DATA, PlotStyle(xlabel="Mi eje")).axes[0].get_xlabel() == "Mi eje"


# ---------- dosis-respuesta ----------
def _dr_data():
    from plotcraft.core.fitting import model
    d = np.repeat([0.01, 0.1, 1, 10, 100, 1000], 3).astype(float)
    rng = np.random.default_rng(1)
    return XYData("Dosis (µM)", list(d), {"A": list(model(d, 3, 100, math.log10(3.0), -1.2) + rng.normal(0, 2, len(d))),
                                          "B": list(model(d, 3, 100, math.log10(40.0), -1.0) + rng.normal(0, 2, len(d)))})


def test_dose_response_draws_means_curve_and_ic50_guides():
    from plotcraft.core.fitting import fit_xy
    xy = _dr_data()
    rep = fit_xy(xy)
    fig = make_xy_figure(xy, PlotStyle(x_log=True), kind="Dosis-respuesta (4PL)", fits=rep.results)
    ax = fig.axes[0]
    curves = [l for l in ax.lines if len(l.get_xdata()) > 100]
    assert len(curves) == 2 and len(ax.containers) == 2                          # curvas + puntos con error
    assert any("IC50 = " in t.get_text() for t in ax.get_legend().get_texts())
    a = rep.results["A"]
    cx, cy = curves[0].get_xdata(), curves[0].get_ydata()
    assert cy == pytest.approx(a.curve(cx))                                      # la curva dibujada ES el ajuste
    guides = [l for l in ax.lines if l.get_linestyle() == ":"]
    assert len(guides) == 2 and guides[0].get_xdata()[0] == pytest.approx(a.ic50)
    assert guides[0].get_ydata()[1] == pytest.approx(float(a.curve(a.ic50)))
    assert ax.get_xscale() == "log" and ax.get_xlabel() == "Dosis (µM)"
    assert not [l for l in make_xy_figure(xy, PlotStyle(), kind="Dosis-respuesta (4PL)", fits=rep.results,
                                          guides=False).axes[0].lines if l.get_linestyle() == ":"]


def test_dose_response_without_fit_shows_only_points():
    ax = make_xy_figure(_dr_data(), PlotStyle(), kind="Dosis-respuesta (4PL)").axes[0]
    assert not [l for l in ax.lines if len(l.get_xdata()) > 100] and len(ax.containers) == 2
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["A", "B"]


def test_project_roundtrip_keeps_fit_config(tmp_path):
    from plotcraft.core.fitting import FitConfig
    f = tmp_path / "f.pcft"
    Project("t", mode="xy", fit=FitConfig(fix_bottom=0.0, fix_top=100.0, alpha=0.01, active=True)).save(f)
    q = Project.load(f)
    assert q.fit == FitConfig(fix_bottom=0.0, fix_top=100.0, alpha=0.01, active=True)
