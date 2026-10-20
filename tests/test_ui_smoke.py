import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from plotcraft.ui.main_window import MainWindow


def test_window_roundtrip():
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.sheet.set_data({"C-": [1.0, 2.0, 3.0], "T1": [4.0, 5.0, 6.0]})
    assert list(w.sheet.get_data()) == ["C-", "T1"]
    w.refresh_plot()
    assert len(w.canvas.figure.axes[0].patches) == 2
    st = w.props.get_style()
    w.props.set_style(st)
    assert w.props.get_style() == st


def test_analysis_flow(tmp_path):
    from plotcraft.core.project import Project
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.sheet.set_data({"A": [10.0, 12, 11, 13, 9], "B": [14.0, 15, 13, 16, 15], "C": [20.0, 19, 22, 21, 18]})
    w.refresh_plot()
    assert w.result is None and not w.canvas.figure.axes[0].texts
    w.analysis.control.count() == 3
    w.analysis._run()
    w.refresh_plot()
    assert w.result.title == "ANOVA de una vía"
    assert len(w.canvas.figure.axes[0].texts) >= 2           # asteriscos
    assert "Tukey" in w.analysis.out.toPlainText()
    # enlace vivo: al cambiar datos se recalcula
    w.sheet.set_data({"A": [10.0, 12, 11], "B": [10.0, 12, 11], "C": [10.5, 11.5, 11]})
    w.refresh_plot()
    assert not w.canvas.figure.axes[0].texts
    # error amable
    w.sheet.set_data({"A": [1.0, 2.0]})
    w.refresh_plot()
    assert "No se pudo analizar" in w.analysis.out.toPlainText()
    # guardar y abrir conserva la configuración
    w.sheet.set_data({"A": [1.0, 2.0, 3], "B": [5.0, 6, 7]})
    w.analysis.test.setCurrentText("t de Student")
    f = tmp_path / "p.pcft"
    w._project().save(f)
    q = Project.load(f)
    assert q.analysis.test == "t de Student" and q.analysis.active


def _td():
    from plotcraft.core.twoway import TwoWayData
    cells = {("Control", "24h"): [10, 12, 11], ("Control", "48h"): [8, 9, 7],
             ("Trat", "24h"): [15, 14, 16], ("Trat", "48h"): [25, 27, 26],
             ("Vehículo", "24h"): [12, 13, 11], ("Vehículo", "48h"): [12, 11, 13]}
    td = TwoWayData("Tratamiento", "Tiempo", "Viabilidad")
    for (a, b), vals in cells.items():
        for v in vals:
            td.a.append(a); td.b.append(b); td.y.append(float(v))
    return td


def test_two_way_flow_and_project_roundtrip(tmp_path):
    from plotcraft.core.project import Project
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.design.setCurrentIndex(1)                       # 2 factores
    assert w.analysis.mode == "dos" and w.analysis.test.currentText() == "ANOVA de dos vías"
    assert "Dunnett" not in [w.analysis.posthoc.itemText(i) for i in range(w.analysis.posthoc.count())]
    w.long_sheet.set_data(_td())
    assert w.long_sheet.get_data().levels_b() == ["24h", "48h"]
    w.analysis._run(); w.refresh_plot()
    assert w.result.title == "ANOVA de dos vías"
    assert "Interacción" in w.analysis.out.toPlainText()
    assert w.canvas.figure.axes[0].get_legend() is not None
    assert len(w.canvas.figure.axes[0].texts) >= 1     # asteriscos de efectos simples
    # intercambiar factores: ahora el eje X es el tiempo
    w.props.swap.setChecked(True); w.refresh_plot()
    assert [t.get_text() for t in w.canvas.figure.axes[0].get_xticklabels()] == ["24h", "48h"]
    w.props.swap.setChecked(False)
    # la configuración de cada diseño es independiente
    w.design.setCurrentIndex(0)
    assert w.analysis.mode == "columnas" and "Kruskal-Wallis" in [
        w.analysis.test.itemText(i) for i in range(w.analysis.test.count())]
    w.sheet.set_data({"A": [1.0, 2, 3], "B": [2.0, 3, 4]})
    w.analysis.test.setCurrentText("Mann-Whitney"); w.analysis._run(); w.refresh_plot()
    assert w.result.title.startswith("Mann-Whitney") and not w.analysis.posthoc.isEnabled()
    f = tmp_path / "p.pcft"
    w._project().save(f)
    q = Project.load(f)
    assert q.mode == "columnas" and q.twoway.levels_a() == ["Control", "Trat", "Vehículo"]
    assert q.analysis.test == "Mann-Whitney" and q.analysis_twoway.active
    w2 = MainWindow(); w2._apply(q)
    assert w2.mode == "columnas" and w2.result.title.startswith("Mann-Whitney")
    w2.design.setCurrentIndex(1); w2.refresh_plot()
    assert w2.result.title == "ANOVA de dos vías"


def test_long_sheet_ignores_incomplete_rows_and_comma_decimals():
    app = QApplication.instance() or QApplication([])
    from plotcraft.ui.long_sheet import LongSheet
    from PySide6.QtWidgets import QTableWidgetItem
    s = LongSheet()
    for r, row in enumerate([("A", "x", "1,5"), ("A", "", "2"), ("B", "x", "abc"), ("B", "y", "3")]):
        for c, v in enumerate(row):
            s.setItem(r, c, QTableWidgetItem(v))
    td = s.get_data()
    assert (td.a, td.b, td.y) == (["A", "B"], ["x", "y"], [1.5, 3.0])


def test_grid_sheets_paste_headers_and_data():
    app = QApplication.instance() or QApplication([])
    from PySide6.QtGui import QGuiApplication
    from plotcraft.ui.grid_sheet import BubbleSheet, XYSheet
    xs = XYSheet()
    QGuiApplication.clipboard().setText("Dosis\tLínea A\tLínea B\tLínea C\tLínea D\n1\t10\t11\t\t5\n1\t12\t13\t\t6\n10,5\t20\t21\t\t7")
    xs.paste()
    xy = xs.get_data()
    assert xy.x_name == "Dosis" and xy.x == [1.0, 1.0, 10.5]
    assert list(xy.series) == ["Línea A", "Línea B", "Línea D"]       # la serie vacía se omite; la tabla creció
    bs = BubbleSheet()
    QGuiApplication.clipboard().setText("Expr\tViab\tDosis\tLínea\n1\t10\t5\tA\n2\t20\t10\tB\nx\t3\t4\tC")
    bs.paste()
    bd = bs.get_data()
    assert (bd.x_name, bd.size_name) == ("Expr", "Dosis") and bd.group == ["A", "B"] and bd.size == [5.0, 10.0]
    xs2 = XYSheet(); xs2.set_data(xy)
    assert xs2.get_data().series["Línea A"] == xy.series["Línea A"]


def test_charts_designs_and_option_visibility(tmp_path):
    from plotcraft.core.project import Project
    from plotcraft.core.xydata import BubbleData, XYData
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show()
    items = lambda: [w.chart.itemText(i) for i in range(w.chart.count())]  # noqa: E731
    vis = lambda widget: widget.isVisibleTo(w.props)  # noqa: E731
    assert items() == ["Barras", "Cajas y bigotes", "Histograma"] and vis(w.props.error) and not vis(w.props.bins)
    # columnas: cajas con análisis y asteriscos
    w.sheet.set_data({"A": [10.0, 12, 11, 13, 9], "B": [14.0, 15, 13, 16, 15], "C": [20.0, 19, 22, 21, 18]})
    w.analysis._run()
    w.chart.setCurrentText("Cajas y bigotes"); w.refresh_plot()
    assert len(w.canvas.figure.axes[0].patches) == 3 and len(w.canvas.figure.axes[0].texts) >= 2
    assert vis(w.props.whisker) and not vis(w.props.error)
    w.chart.setCurrentText("Histograma"); w.refresh_plot()
    assert vis(w.props.bins) and vis(w.props.density) and len(w.canvas.figure.axes[0].patches) > 3
    # 2 factores
    w.design.setCurrentIndex(1)
    assert items() == ["Barras agrupadas", "Cajas agrupadas"] and vis(w.props.swap)
    # XY: sin análisis, opciones propias
    w.design.setCurrentIndex(2)
    assert items() == ["Dispersión", "Líneas y puntos", "Líneas", "Dosis-respuesta (4PL)"]
    assert not w.analysis.box.isEnabled() and not w.analysis.run_btn.isEnabled()
    assert "todavía no tiene análisis" in w.analysis.out.toPlainText()
    w.xy_sheet.set_data(XYData("Dosis", [1.0, 1, 2, 2], {"A": [1.0, 1.2, 2, 2.2]}))
    w.chart.setCurrentText("Dispersión"); w.refresh_plot()
    assert vis(w.props.trend) and vis(w.props.marker) and not vis(w.props.average)
    assert len(w.canvas.figure.axes[0].collections[0].get_offsets()) == 4
    w.chart.setCurrentText("Líneas y puntos"); w.refresh_plot()
    assert vis(w.props.average) and not vis(w.props.trend)
    # burbujas
    w.design.setCurrentIndex(3)
    assert items() == ["Burbujas"] and vis(w.props.bubble)
    w.bubble_sheet.set_data(BubbleData("x", "y", "s", "g", [1.0, 2], [1.0, 2], [3.0, 9.0], ["a", "b"]))
    w.refresh_plot()
    assert len(w.canvas.figure.axes[0].collections) >= 2
    # guardar/abrir en modo burbujas conserva todo
    f = tmp_path / "b.pcft"
    w._project().save(f)
    q = Project.load(f)
    assert q.mode == "burbujas" and q.style.chart == "Burbujas" and q.bubble.size == [3.0, 9.0]
    w2 = MainWindow(); w2._apply(q)
    assert w2.mode == "burbujas" and not w2.analysis.box.isEnabled()
    # volver a un diseño con análisis restaura su estado
    w.design.setCurrentIndex(0)
    assert w.analysis.box.isEnabled() and w.analysis.get_config().active


def test_dose_response_flow_in_the_window(tmp_path):
    import math
    import numpy as np
    from plotcraft.core.fitting import model
    from plotcraft.core.project import Project
    from plotcraft.core.xydata import XYData
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show()
    w.design.setCurrentIndex(2)
    assert w.analysis_stack.currentWidget() is w.fit_panel          # XY muestra el panel de ajuste
    d = np.repeat([0.01, 0.1, 1, 10, 100, 1000], 3).astype(float)
    y = model(d, 2, 100, math.log10(8.0), -1.1) + np.random.default_rng(4).normal(0, 2, len(d))
    w.xy_sheet.set_data(XYData("Dosis", list(d), {"Línea A": list(y)}))
    w.chart.setCurrentText("Dosis-respuesta (4PL)")
    assert w.props.xlog.isChecked()                                  # entra en escala log
    w.refresh_plot()
    assert w.fit is None and "Ejecutar ajuste" in w.fit_panel.out.toPlainText()
    w.fit_panel.bottom.set_value(0.0); w.fit_panel.top.set_value(100.0)
    w.fit_panel._run(); w.refresh_plot()
    r = w.fit.results["Línea A"]
    assert r.ic50 == pytest.approx(8.0, rel=0.2) and r.params["bottom"].fixed
    text = w.fit_panel.out.toPlainText()
    assert "IC50" in text and "(fijo)" in text and "IC95%" in text
    assert any("IC50 = " in t.get_text() for t in w.canvas.figure.axes[0].get_legend().get_texts())
    # caché: cambiar solo el estilo no reajusta
    key = w._fit_cache[0]; report = w._fit_cache[1]
    w.props.palette_box.setCurrentText("Clásica"); w.refresh_plot()
    assert w._fit_cache[1] is report and w._fit_cache[0] == key
    w.fit_panel.conf.setCurrentText("99%"); w.refresh_plot()          # cambiar el nivel de confianza sí reajusta
    assert w._fit_cache[1] is not report and "IC99%" in w.fit_panel.out.toPlainText()
    # otro gráfico: el ajuste se muestra y avisa cómo ver la curva
    w.chart.setCurrentText("Dispersión"); w.refresh_plot()
    assert "elige Gráfico" in w.fit_panel.out.toPlainText()
    w.chart.setCurrentText("Dosis-respuesta (4PL)"); w.refresh_plot()
    # guardar / abrir conserva la configuración y vuelve a ajustar
    f = tmp_path / "dr.pcft"
    w._project().save(f)
    q = Project.load(f)
    assert q.fit.active and q.fit.fix_top == 100.0 and q.style.chart == "Dosis-respuesta (4PL)"
    w2 = MainWindow(); w2._apply(q)
    assert w2.fit.results["Línea A"].ic50 == pytest.approx(r.ic50, rel=1e-3) and w2.analysis_stack.currentWidget() is w2.fit_panel
    # los datos cambian -> el ajuste se actualiza solo (enlace vivo)
    w2.xy_sheet.set_data(XYData("Dosis", list(d), {"Línea A": list(model(d, 0, 100, math.log10(50.0), -1.0))}))
    w2.refresh_plot()
    assert w2.fit.results["Línea A"].ic50 == pytest.approx(50.0, rel=1e-3)
    # un error de datos se muestra sin tumbar la ventana
    w2.xy_sheet.set_data(XYData("Dosis", [1.0, 2.0], {"A": [1.0, 2.0]}))
    w2.refresh_plot()
    assert "3 dosis" in w2.fit_panel.out.toPlainText()
    w2.design.setCurrentIndex(0)
    assert w2.analysis_stack.currentWidget() is w2.analysis
