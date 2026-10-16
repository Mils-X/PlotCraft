from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QLineEdit, QSpinBox, QVBoxLayout, QWidget)

from plotcraft.core.stats import ERROR_TYPES
from plotcraft.core.style import PALETTES, PlotStyle


class _OptionalNumber(QWidget):
    """Número opcional: 'Auto' cuando está vacío."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Auto")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.edit)
        self.edit.textChanged.connect(lambda _: self.changed.emit())

    def value(self) -> float | None:
        try:
            return float(self.edit.text().replace(",", "."))
        except ValueError:
            return None

    def set_value(self, v: float | None) -> None:
        self.edit.setText("" if v is None else f"{v:g}")


class PropertiesPanel(QWidget):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.error = QComboBox(); self.error.addItems(ERROR_TYPES)
        self.palette_box = QComboBox(); self.palette_box.addItems(PALETTES)
        self.points = QCheckBox("Mostrar puntos individuales")
        self.title = QLineEdit(); self.xlabel = QLineEdit(); self.ylabel = QLineEdit()
        self.ymin = _OptionalNumber(); self.ymax = _OptionalNumber()
        self.font = QSpinBox(); self.font.setRange(6, 30)
        self.rotation = QComboBox(); self.rotation.addItems(["auto", "0", "45", "90"])
        self.width = QDoubleSpinBox(); self.width.setRange(2, 20)
        self.height = QDoubleSpinBox(); self.height.setRange(2, 20)

        basic = QGroupBox("Básico")
        f = QFormLayout(basic)
        f.addRow("Error", self.error)
        f.addRow("Colores", self.palette_box)
        f.addRow("Título", self.title)
        f.addRow("Eje X", self.xlabel)
        f.addRow("Eje Y", self.ylabel)
        f.addRow(self.points)

        adv = QGroupBox("Avanzado")
        adv.setCheckable(True); adv.setChecked(False)  # divulgación progresiva
        g = QFormLayout(adv)
        g.addRow("Y mínimo", self.ymin)
        g.addRow("Y máximo", self.ymax)
        g.addRow("Fuente", self.font)
        g.addRow("Giro etiquetas", self.rotation)
        g.addRow("Ancho (in)", self.width)
        g.addRow("Alto (in)", self.height)
        self._adv_widgets = [adv.layout().itemAt(i).widget() for i in range(adv.layout().count())
                             if adv.layout().itemAt(i).widget()]

        lay = QVBoxLayout(self)
        lay.addWidget(basic); lay.addWidget(adv); lay.addStretch()
        self.setMinimumWidth(240)
        self.set_style(PlotStyle())

        for w in (self.error, self.palette_box, self.rotation):
            w.currentTextChanged.connect(lambda _: self.changed.emit())
        for w in (self.title, self.xlabel, self.ylabel):
            w.textChanged.connect(lambda _: self.changed.emit())
        for w in (self.font, self.width, self.height):
            w.valueChanged.connect(lambda _: self.changed.emit())
        self.points.toggled.connect(lambda _: self.changed.emit())
        self.ymin.changed.connect(self.changed.emit)
        self.ymax.changed.connect(self.changed.emit)

    def get_style(self) -> PlotStyle:
        return PlotStyle(
            error_type=self.error.currentText(), palette=self.palette_box.currentText(),
            title=self.title.text(), xlabel=self.xlabel.text(), ylabel=self.ylabel.text(),
            ymin=self.ymin.value(), ymax=self.ymax.value(), show_points=self.points.isChecked(),
            font_size=self.font.value(), label_rotation=self.rotation.currentText(),
            width=self.width.value(), height=self.height.value(),
        )

    def set_style(self, s: PlotStyle) -> None:
        widgets = [self.error, self.palette_box, self.title, self.xlabel, self.ylabel, self.points,
                   self.font, self.rotation, self.width, self.height, self.ymin.edit, self.ymax.edit]
        blockers = [QSignalBlocker(w) for w in widgets]
        self.error.setCurrentText(s.error_type); self.palette_box.setCurrentText(s.palette)
        self.title.setText(s.title); self.xlabel.setText(s.xlabel); self.ylabel.setText(s.ylabel)
        self.points.setChecked(s.show_points); self.font.setValue(s.font_size)
        self.rotation.setCurrentText(s.label_rotation)
        self.width.setValue(s.width); self.height.setValue(s.height)
        self.ymin.set_value(s.ymin); self.ymax.set_value(s.ymax)
        del blockers
        self.changed.emit()
