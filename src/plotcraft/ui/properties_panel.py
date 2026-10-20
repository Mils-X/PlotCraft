from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QLineEdit, QSpinBox, QVBoxLayout, QWidget)

from plotcraft.core.stats import ERROR_TYPES
from plotcraft.core.style import OPTION_CHARTS, PALETTES, WHISKERS, PlotStyle
from plotcraft.ui.widgets import OptionalNumber as _OptionalNumber


class PropertiesPanel(QWidget):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._loading = False
        self.error = QComboBox(); self.error.addItems(ERROR_TYPES)
        self.palette_box = QComboBox(); self.palette_box.addItems(PALETTES)
        self.points = QCheckBox("Mostrar puntos individuales")
        self.swap = QCheckBox("Intercambiar factores (2 factores)")
        self.title = QLineEdit(); self.xlabel = QLineEdit(); self.ylabel = QLineEdit()
        for w in (self.title, self.xlabel, self.ylabel):
            w.setPlaceholderText("Auto")
        self.ymin = _OptionalNumber(); self.ymax = _OptionalNumber()
        self.font = QSpinBox(); self.font.setRange(6, 30)
        self.rotation = QComboBox(); self.rotation.addItems(["auto", "0", "45", "90"])
        self.width = QDoubleSpinBox(); self.width.setRange(2, 20)
        self.height = QDoubleSpinBox(); self.height.setRange(2, 20)
        # opciones propias de cada tipo de gráfico
        self.whisker = QComboBox(); self.whisker.addItems(WHISKERS)
        self.bins = QSpinBox(); self.bins.setRange(0, 200); self.bins.setSpecialValueText("Auto")
        self.density = QCheckBox("Densidad (en vez de frecuencia)")
        self.marker = QDoubleSpinBox(); self.marker.setRange(1, 30)
        self.line_w = QDoubleSpinBox(); self.line_w.setRange(0.5, 8); self.line_w.setSingleStep(0.5)
        self.average = QCheckBox("Promediar réplicas con el mismo X")
        self.trend = QCheckBox("Línea de tendencia lineal (R²)")
        self.xlog = QCheckBox("Eje X logarítmico")
        self.ylog = QCheckBox("Eje Y logarítmico")
        self.bubble = QDoubleSpinBox(); self.bubble.setRange(0.2, 5); self.bubble.setSingleStep(0.2)

        basic = QGroupBox("Básico")
        self._basic = QFormLayout(basic)
        for label, w in [("Error", self.error), ("Colores", self.palette_box), ("Título", self.title),
                         ("Eje X", self.xlabel), ("Eje Y", self.ylabel)]:
            self._basic.addRow(label, w)
        self._basic.addRow(self.points)
        self._basic.addRow(self.swap)

        specific = QGroupBox("Opciones del gráfico")
        self._spec = QFormLayout(specific)
        self._spec.addRow("Bigotes", self.whisker)
        self._spec.addRow("Intervalos (bins)", self.bins)
        self._spec.addRow(self.density)
        self._spec.addRow("Tamaño marcador", self.marker)
        self._spec.addRow("Grosor de línea", self.line_w)
        self._spec.addRow(self.average)
        self._spec.addRow(self.trend)
        self._spec.addRow(self.xlog)
        self._spec.addRow(self.ylog)
        self._spec.addRow("Escala burbujas", self.bubble)
        self._spec_box = specific

        adv = QGroupBox("Avanzado")
        adv.setCheckable(True); adv.setChecked(False)  # divulgación progresiva
        g = QFormLayout(adv)
        g.addRow("Y mínimo", self.ymin)
        g.addRow("Y máximo", self.ymax)
        g.addRow("Fuente", self.font)
        g.addRow("Giro etiquetas", self.rotation)
        g.addRow("Ancho (in)", self.width)
        g.addRow("Alto (in)", self.height)

        lay = QVBoxLayout(self)
        lay.addWidget(basic); lay.addWidget(specific); lay.addWidget(adv); lay.addStretch()
        self.setMinimumWidth(250)
        self.set_style(PlotStyle())
        self.set_chart("Barras")

        for w in (self.error, self.palette_box, self.rotation, self.whisker):
            w.currentTextChanged.connect(self._emit)
        for w in (self.title, self.xlabel, self.ylabel):
            w.textChanged.connect(self._emit)
        for w in (self.font, self.width, self.height, self.bins, self.marker, self.line_w, self.bubble):
            w.valueChanged.connect(self._emit)
        for w in (self.points, self.swap, self.density, self.average, self.trend, self.xlog, self.ylog):
            w.toggled.connect(self._emit)
        self.ymin.changed.connect(self._emit)
        self.ymax.changed.connect(self._emit)

    def _emit(self, *_) -> None:
        if not self._loading:
            self.changed.emit()

    def set_chart(self, chart: str) -> None:
        """Muestra solo las opciones que tienen sentido para el tipo de gráfico."""
        vis = lambda key: chart in OPTION_CHARTS[key]  # noqa: E731
        self._basic.setRowVisible(self.error, vis("error"))
        self._basic.setRowVisible(self.points, vis("points"))
        self._basic.setRowVisible(self.swap, vis("swap"))
        for key, w in [("whisker", self.whisker), ("bins", self.bins), ("density", self.density),
                       ("marker", self.marker), ("line_width", self.line_w), ("average", self.average),
                       ("trend", self.trend), ("x_log", self.xlog), ("y_log", self.ylog),
                       ("bubble", self.bubble)]:
            self._spec.setRowVisible(w, vis(key))
        self._spec_box.setVisible(any(vis(k) for k in ("whisker", "bins", "density", "marker", "line_width",
                                                       "average", "trend", "x_log", "y_log", "bubble")))

    def get_style(self) -> PlotStyle:
        return PlotStyle(
            error_type=self.error.currentText(), palette=self.palette_box.currentText(),
            title=self.title.text(), xlabel=self.xlabel.text(), ylabel=self.ylabel.text(),
            ymin=self.ymin.value(), ymax=self.ymax.value(), show_points=self.points.isChecked(),
            swap_factors=self.swap.isChecked(), font_size=self.font.value(),
            label_rotation=self.rotation.currentText(), width=self.width.value(), height=self.height.value(),
            whisker=self.whisker.currentText(), bins=self.bins.value(), density=self.density.isChecked(),
            marker_size=self.marker.value(), line_width=self.line_w.value(),
            average_reps=self.average.isChecked(), trendline=self.trend.isChecked(),
            x_log=self.xlog.isChecked(), y_log=self.ylog.isChecked(), bubble_scale=self.bubble.value())

    def set_style(self, s: PlotStyle) -> None:
        self._loading = True
        self.error.setCurrentText(s.error_type); self.palette_box.setCurrentText(s.palette)
        self.title.setText(s.title); self.xlabel.setText(s.xlabel); self.ylabel.setText(s.ylabel)
        self.points.setChecked(s.show_points); self.swap.setChecked(s.swap_factors)
        self.font.setValue(s.font_size); self.rotation.setCurrentText(s.label_rotation)
        self.width.setValue(s.width); self.height.setValue(s.height)
        self.ymin.set_value(s.ymin); self.ymax.set_value(s.ymax)
        self.whisker.setCurrentText(s.whisker); self.bins.setValue(s.bins); self.density.setChecked(s.density)
        self.marker.setValue(s.marker_size); self.line_w.setValue(s.line_width)
        self.average.setChecked(s.average_reps); self.trend.setChecked(s.trendline)
        self.xlog.setChecked(s.x_log); self.ylog.setChecked(s.y_log); self.bubble.setValue(s.bubble_scale)
        self._loading = False
        self.changed.emit()
