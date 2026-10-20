from __future__ import annotations

import html

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from plotcraft.core.fitting import FitConfig
from plotcraft.ui.widgets import OptionalNumber

CONFIDENCE = {"95%": 0.05, "99%": 0.01, "90%": 0.10}
PLACEHOLDER = ("<p style='color:gray'>Pon la <b>dosis en la columna X</b> y las <b>respuestas en las columnas Y</b> "
               "(una serie por columna; las filas con la misma dosis son réplicas) y pulsa "
               "<b>Ejecutar ajuste</b>. Para ver la curva elige <b>Gráfico ▸ Dosis-respuesta (4PL)</b>. "
               "Las dosis ≤ 0 (por ejemplo un control sin tratar) no entran en el ajuste.</p>")


class FitPanel(QWidget):
    """Ajuste dosis-respuesta de 4 parámetros para el diseño XY."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self._loading = False
        self.bottom = OptionalNumber("Libre"); self.top = OptionalNumber("Libre"); self.hill = OptionalNumber("Libre")
        self.conf = QComboBox(); self.conf.addItems(CONFIDENCE)
        self.guides = QCheckBox("Mostrar guías del IC50 en el gráfico"); self.guides.setChecked(True)
        self.run_btn = QPushButton("Ejecutar ajuste")
        self.out = QTextBrowser(); self.out.setHtml(PLACEHOLDER)

        box = QGroupBox("Ajuste dosis-respuesta de 4 parámetros")
        f = QFormLayout(box)
        f.addRow(QLabel("Y = Bottom + (Top − Bottom) / (1 + 10^((LogIC50 − log X) · Hill))"))
        f.addRow("Fijar Bottom en", self.bottom)
        f.addRow("Fijar Top en", self.top)
        f.addRow("Fijar pendiente de Hill en", self.hill)
        f.addRow("Nivel de confianza", self.conf)
        f.addRow(self.guides)
        f.addRow(QLabel("<i>Deja «Libre» para estimar el parámetro. Con viabilidad normalizada suele fijarse "
                        "Bottom = 0 y Top = 100.</i>"))
        row = QHBoxLayout(); row.addWidget(self.run_btn); row.addStretch()
        lay = QVBoxLayout(self)
        lay.addWidget(box); lay.addLayout(row); lay.addWidget(self.out, 1)

        self.run_btn.clicked.connect(self._run)
        for w in (self.bottom, self.top, self.hill):
            w.changed.connect(self._cfg_changed)
        self.conf.currentTextChanged.connect(self._cfg_changed)
        self.guides.toggled.connect(self._cfg_changed)

    def _run(self) -> None:
        self.active = True
        self.changed.emit()

    def _cfg_changed(self, *_) -> None:
        if self.active and not self._loading:
            self.changed.emit()

    def get_config(self) -> FitConfig:
        return FitConfig(fix_bottom=self.bottom.value(), fix_top=self.top.value(), fix_hill=self.hill.value(),
                         alpha=CONFIDENCE[self.conf.currentText()], show_guides=self.guides.isChecked(),
                         active=self.active)

    def set_config(self, c: FitConfig) -> None:
        self._loading = True
        self.bottom.set_value(c.fix_bottom); self.top.set_value(c.fix_top); self.hill.set_value(c.fix_hill)
        label = next((k for k, v in CONFIDENCE.items() if abs(v - c.alpha) < 1e-9), "95%")
        self.conf.setCurrentText(label)
        self.guides.setChecked(c.show_guides)
        self.active = c.active
        self._loading = False
        if not c.active:
            self.out.setHtml(PLACEHOLDER)
        self.changed.emit()

    def show_html(self, body: str) -> None:
        self.out.setHtml(body)

    def show_error(self, msg: str) -> None:
        self.out.setHtml(f"<p style='color:#c0392b'><b>No se pudo ajustar:</b> {html.escape(msg)}</p>")
