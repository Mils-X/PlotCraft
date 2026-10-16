from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QMainWindow, QMessageBox, QSplitter, QTabWidget,
                               QTreeWidget, QTreeWidgetItem)

from plotcraft.core.project import Project
from plotcraft.ui.data_sheet import DataSheet
from plotcraft.ui.plot_canvas import PlotCanvas
from plotcraft.ui.properties_panel import PropertiesPanel

PROJECT_FILTER = "Proyecto PlotCraft (*.pcft)"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.path: Path | None = None
        self.resize(1200, 700)

        self.sheet = DataSheet()
        self.canvas = PlotCanvas()
        self.props = PropertiesPanel()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.sheet, "Datos")
        self.tabs.addTab(self.canvas, "Gráfico")

        self.tree = QTreeWidget(); self.tree.setHeaderLabel("Proyecto")
        root = QTreeWidgetItem(self.tree, ["Tabla 1"])
        QTreeWidgetItem(root, ["Datos"]); QTreeWidgetItem(root, ["Gráfico"])
        self.tree.expandAll()
        self.tree.itemClicked.connect(self._tree_clicked)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.tree); split.addWidget(self.tabs); split.addWidget(self.props)
        split.setSizes([160, 780, 260])
        self.setCentralWidget(split)

        self._timer = QTimer(singleShot=True, interval=150)  # evita redibujar en cada tecla
        self._timer.timeout.connect(self.refresh_plot)
        self.sheet.data_changed.connect(self._timer.start)
        self.props.changed.connect(self._timer.start)

        self._build_menu()
        self.refresh_plot()
        self._update_title()

    # --- menú -------------------------------------------------------------
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

    def _tree_clicked(self, item: QTreeWidgetItem) -> None:
        if item.text(0) == "Datos":
            self.tabs.setCurrentWidget(self.sheet)
        elif item.text(0) == "Gráfico":
            self.tabs.setCurrentWidget(self.canvas)

    # --- acciones ---------------------------------------------------------
    def refresh_plot(self) -> None:
        self.canvas.draw_plot(self.sheet.get_data(), self.props.get_style())

    def _project(self) -> Project:
        return Project(self.path.stem if self.path else "Sin título",
                       self.sheet.get_data(), self.props.get_style())

    def _update_title(self) -> None:
        self.setWindowTitle(f"PlotCraft — {self.path.name if self.path else 'Sin título'}")

    def new_project(self) -> None:
        self.path = None
        self.sheet.set_data({})
        self.props.set_style(Project().style)
        self._update_title()

    def open_project(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "", PROJECT_FILTER)
        if not fn:
            return
        try:
            p = Project.load(fn)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error al abrir", str(e))
            return
        self.path = Path(fn)
        self.sheet.set_data(p.data)
        self.props.set_style(p.style)
        self._update_title()

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
            self.canvas.figure.savefig(fn, dpi=300, bbox_inches="tight")
