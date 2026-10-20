from __future__ import annotations

import json
from pathlib import Path

from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QComboBox, QFileDialog, QLabel, QMainWindow, QMessageBox, QSplitter,
                               QStackedWidget, QTabWidget, QToolBar, QTreeWidget, QTreeWidgetItem)

from plotcraft.core.analysis import (AnalysisConfig, analyze, analyze_twoway, result_to_html,
                                     significance_labels)
from plotcraft.core.fitting import fit_to_html, fit_xy
from plotcraft.core.plots_box_hist import make_box_figure, make_grouped_box_figure, make_hist_figure
from plotcraft.core.plots_xy import make_bubble_figure, make_xy_figure
from plotcraft.core.plotting import make_bar_figure, make_grouped_figure
from plotcraft.core.project import Project
from plotcraft.core.style import CHARTS, DOSE_RESPONSE
from plotcraft.ui.analysis_panel import AnalysisPanel
from plotcraft.ui.data_sheet import DataSheet
from plotcraft.ui.fit_panel import FitPanel
from plotcraft.ui.grid_sheet import BubbleSheet, XYSheet
from plotcraft.ui.long_sheet import LongSheet
from plotcraft.ui.plot_canvas import PlotCanvas
from plotcraft.ui.properties_panel import PropertiesPanel

PROJECT_FILTER = "Proyecto PlotCraft (*.pcft)"
DESIGNS = (("columnas", "1 factor — un grupo por columna"), ("dos", "2 factores — formato largo"),
           ("xy", "XY — X y una o más series Y"), ("burbujas", "Burbujas — X, Y, tamaño"))
MODES = [m for m, _ in DESIGNS]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.path: Path | None = None
        self.resize(1200, 700)

        self.sheet = DataSheet()
        self.long_sheet = LongSheet()
        self.xy_sheet = XYSheet()
        self.bubble_sheet = BubbleSheet()
        self.canvas = PlotCanvas()
        self.props = PropertiesPanel()
        self.analysis = AnalysisPanel()
        self.fit_panel = FitPanel()
        self.analysis_stack = QStackedWidget()
        self.analysis_stack.addWidget(self.analysis)
        self.analysis_stack.addWidget(self.fit_panel)
        self.fit = None            # FitReport del último ajuste
        self._fit_cache = None     # (clave, FitReport): evita reajustar si solo cambió el estilo
        self._comps = None
        self.result = None
        self._builder = None

        self.stack = QStackedWidget()
        for w in (self.sheet, self.long_sheet, self.xy_sheet, self.bubble_sheet):  # mismo orden que DESIGNS
            self.stack.addWidget(w)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.stack, "Datos")
        self.tabs.addTab(self.canvas, "Gráfico")
        self.tabs.addTab(self.analysis_stack, "Análisis")

        bar = QToolBar("Diseño"); bar.setMovable(False)
        bar.addWidget(QLabel("  Diseño de datos: "))
        self.design = QComboBox()
        for _, label in DESIGNS:
            self.design.addItem(label)
        bar.addWidget(self.design)
        bar.addWidget(QLabel("   Gráfico: "))
        self.chart = QComboBox()
        self.chart.addItems(CHARTS["columnas"])
        bar.addWidget(self.chart)
        self.addToolBar(bar)
        self.design.currentIndexChanged.connect(self._design_changed)
        self.chart.currentTextChanged.connect(self._chart_changed)

        self.tree = QTreeWidget(); self.tree.setHeaderLabel("Proyecto")
        root = QTreeWidgetItem(self.tree, ["Tabla 1"])
        for name in ("Datos", "Gráfico", "Análisis"):
            QTreeWidgetItem(root, [name])
        self.tree.expandAll()
        self.tree.itemClicked.connect(self._tree_clicked)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.tree); split.addWidget(self.tabs); split.addWidget(self.props)
        split.setSizes([160, 780, 260])
        self.setCentralWidget(split)

        self._timer = QTimer(singleShot=True, interval=150)  # evita redibujar en cada tecla
        self._timer.timeout.connect(self.refresh_plot)
        for sig in (self.sheet.data_changed, self.long_sheet.data_changed, self.xy_sheet.data_changed,
                    self.bubble_sheet.data_changed, self.props.changed, self.analysis.changed,
                    self.fit_panel.changed):
            sig.connect(self._timer.start)

        self._build_menu()
        self.props.set_chart(self.chart.currentText())
        self.refresh_plot()
        self._update_title()

    @property
    def mode(self) -> str:
        return MODES[self.design.currentIndex()]

    # --- menú y navegación -------------------------------------------------
    def _build_menu(self) -> None:
        m = self.menuBar().addMenu("&Archivo")
        for text, key, slot in [
            ("&Nuevo", QKeySequence.New, self.new_project),
            ("&Abrir…", QKeySequence.Open, self.open_project),
            ("&Guardar", QKeySequence.Save, self.save_project),
            ("Guardar &como…", QKeySequence.SaveAs, self.save_project_as),
            ("&Exportar gráfico…", "Ctrl+E", self.export_figure),
            ("&Salir", QKeySequence.Quit, self.close),
        ]:
            act = QAction(text, self, triggered=slot)
            act.setShortcut(key)
            m.addAction(act)
        # Editar: actúa sobre la hoja visible. Sin atajos de ventana (los maneja la hoja al tener el foco)
        self.menu_edit = self.menuBar().addMenu("&Editar")
        self._edit_actions = {}
        for key, text, slot in [
            ("cut", "Cortar\tCtrl+X", lambda: self._sheet_call("cut_selection")),
            ("copy", "Copiar\tCtrl+C", lambda: self._sheet_call("copy_selection")),
            ("paste", "Pegar\tCtrl+V", lambda: self._sheet_call("paste")),
            ("clear", "Borrar contenido\tSupr", lambda: self._sheet_call("clear_selection")),
            ("insert", "Insertar columna a la derecha", lambda: self._sheet_call("insert_column_right")),
            ("delete", "Eliminar columna(s) seleccionada(s)", lambda: self._sheet_call("delete_selected_columns")),
        ]:
            if key == "insert":
                self.menu_edit.addSeparator()
            self._edit_actions[key] = self.menu_edit.addAction(text, slot)
        self.menu_edit.aboutToShow.connect(self._update_edit_menu)

    def _sheet_call(self, name: str) -> None:
        getattr(self.stack.currentWidget(), name)()

    def _update_edit_menu(self) -> None:
        on_data = self.tabs.currentWidget() is self.stack
        growable = on_data and self.stack.currentWidget().growable
        for k, a in self._edit_actions.items():
            a.setEnabled(on_data and (growable or k not in ("insert", "delete")))

    def _tree_clicked(self, item: QTreeWidgetItem) -> None:
        target = {"Datos": self.stack, "Gráfico": self.canvas, "Análisis": self.analysis_stack}.get(item.text(0))
        if target is not None:
            self.tabs.setCurrentWidget(target)

    def _set_chart_items(self, mode: str, keep: str | None = None) -> None:
        items = CHARTS[mode]
        self.chart.blockSignals(True)
        self.chart.clear(); self.chart.addItems(items)
        self.chart.setCurrentText(keep if keep in items else items[0])
        self.chart.blockSignals(False)
        self.props.set_chart(self.chart.currentText())

    def _set_analysis_view(self, mode: str) -> None:
        self.analysis_stack.setCurrentWidget(self.fit_panel if mode == "xy" else self.analysis)

    def _design_changed(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        self._set_analysis_view(MODES[idx])
        self._set_chart_items(MODES[idx])
        self.analysis.set_mode(MODES[idx])
        self.refresh_plot()

    def _chart_changed(self, chart: str) -> None:
        if chart:
            self.props.set_chart(chart)
            if chart == DOSE_RESPONSE and not self.props.xlog.isChecked():
                self.props.xlog.setChecked(True)   # las curvas dosis-respuesta se ven en escala log; se puede desmarcar
            self.refresh_plot()

    # --- análisis y gráfico --------------------------------------------------
    def _style(self):
        style = self.props.get_style()
        style.chart = self.chart.currentText()
        return style

    def refresh_plot(self) -> None:
        """Recalcula el análisis (si está activo) y redibuja el gráfico."""
        style = self._style()
        chart = style.chart
        self._comps, self.result = None, None
        mode = self.mode
        if mode == "columnas":
            data = self.sheet.get_data()
            self.analysis.set_groups(list(data))
            cfg = self.analysis.get_config()
            self._run(cfg, lambda: analyze(data, cfg))
            comps = self._comps
            fn = {"Barras": make_bar_figure, "Cajas y bigotes": make_box_figure,
                  "Histograma": make_hist_figure}[chart]
            self._builder = lambda fig, apply: fn(data, style, fig, apply, comparisons=comps)
        elif mode == "dos":
            td = self.long_sheet.get_data()
            if style.swap_factors:
                td = td.swapped()
            cfg = self.analysis.get_config()
            self._run(cfg, lambda: analyze_twoway(td, cfg))
            comps = self._comps
            fn = {"Barras agrupadas": make_grouped_figure, "Cajas agrupadas": make_grouped_box_figure}[chart]
            self._builder = lambda fig, apply: fn(td, style, fig, apply, comparisons=comps)
        elif mode == "xy":
            xy = self.xy_sheet.get_data()
            fits, guides = self._run_fit(xy, chart)
            self._builder = lambda fig, apply: make_xy_figure(xy, style, fig, apply, kind=chart, fits=fits, guides=guides)
        else:
            bd = self.bubble_sheet.get_data()
            self._builder = lambda fig, apply: make_bubble_figure(bd, style, fig, apply)
        self.canvas.draw_with(lambda fig: self._builder(fig, False))

    def _run_fit(self, xy, chart: str):
        """Ajuste 4PL (con caché). Devuelve (resultados por serie, mostrar guías)."""
        cfg = self.fit_panel.get_config()
        self.fit = None
        if not cfg.active:
            return None, cfg.show_guides
        key = (json.dumps(xy.to_dict()), cfg.fix_bottom, cfg.fix_top, cfg.fix_hill, cfg.alpha)
        if self._fit_cache is None or self._fit_cache[0] != key:
            try:
                self._fit_cache = (key, fit_xy(xy, cfg))
            except Exception as e:  # noqa: BLE001
                self._fit_cache = None
                self.fit_panel.show_error(str(e))
                return None, cfg.show_guides
        self.fit = self._fit_cache[1]
        body = fit_to_html(self.fit, cfg)
        if chart != DOSE_RESPONSE:
            body += "<p><b>Para ver la curva en el gráfico, elige Gráfico ▸ Dosis-respuesta (4PL).</b></p>"
        self.fit_panel.show_html(body)
        return self.fit.results, cfg.show_guides

    def _run(self, cfg: AnalysisConfig, fn) -> None:
        if not cfg.active:
            return
        try:
            self.result = fn()
            self.analysis.show_html(result_to_html(self.result))
            if cfg.show_stars:
                self._comps = significance_labels(self.result, cfg.show_ns)
        except Exception as e:  # noqa: BLE001
            self.analysis.show_error(str(e))

    # --- proyecto ------------------------------------------------------------
    def _project(self) -> Project:
        cols, dos = self.analysis.get_configs()
        return Project(self.path.stem if self.path else "Sin título", self.sheet.get_data(), self._style(),
                       cols, self.mode, self.long_sheet.get_data(), dos,
                       self.xy_sheet.get_data(), self.bubble_sheet.get_data(), self.fit_panel.get_config())

    def _update_title(self) -> None:
        self.setWindowTitle(f"PlotCraft — {self.path.name if self.path else 'Sin título'}")

    def _apply(self, p: Project) -> None:
        self.sheet.set_data(p.data)
        self.long_sheet.set_data(p.twoway)
        self.xy_sheet.set_data(p.xy)
        self.bubble_sheet.set_data(p.bubble)
        self.props.set_style(p.style)
        mode = p.mode if p.mode in MODES else "columnas"
        idx = MODES.index(mode)
        self.design.blockSignals(True)
        self.design.setCurrentIndex(idx)
        self.design.blockSignals(False)
        self.stack.setCurrentIndex(idx)
        self._set_chart_items(mode, p.style.chart)
        self.analysis.set_configs(p.analysis, p.analysis_twoway, mode)
        self.fit_panel.set_config(p.fit)
        self._set_analysis_view(mode)
        self.refresh_plot()
        self._update_title()

    def new_project(self) -> None:
        self.path = None
        self._apply(Project())

    def open_project(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "", PROJECT_FILTER)
        if fn:
            self.open_path(fn)

    def open_path(self, fn: str) -> bool:
        """Abre un proyecto .pcft (también desde la línea de comandos o al hacer doble clic)."""
        try:
            p = Project.load(fn)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error al abrir", f"No se pudo abrir «{fn}»:\n{e}")
            return False
        self.path = Path(fn).resolve()
        self._apply(p)
        return True

    def save_project(self) -> None:
        if self.path is None:
            return self.save_project_as()
        self._project().save(self.path)

    def save_project_as(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", "proyecto.pcft", PROJECT_FILTER)
        if fn:
            self.path = Path(fn if fn.endswith(".pcft") else fn + ".pcft")
            self._project().save(self.path)
            self._update_title()

    def export_figure(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(
            self, "Exportar gráfico", "grafico.png", "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)")
        if fn:
            # figura nueva con el tamaño Ancho/Alto del panel avanzado
            fig = Figure()
            self._builder(fig, True)
            fig.savefig(fn, dpi=300, bbox_inches="tight")
