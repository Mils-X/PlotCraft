from __future__ import annotations

import html

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from plotcraft.core.analysis import TESTS, TESTS_TWO, AnalysisConfig, posthoc_choices
from plotcraft.core.twoway import COMPARE_MODES

ALPHAS = ("0.05", "0.01", "0.10")
NO_ANALYSIS = ("<p style='color:gray'>Este diseño de datos todavía no tiene análisis estadístico "
               "(la correlación llegará más adelante). Usa <b>1 factor</b> o <b>2 factores</b> para t-test, ANOVA "
               "y pruebas no paramétricas, y <b>XY</b> para curvas dosis-respuesta.</p>")
PLACEHOLDERS = {
    "columnas": ("<p style='color:gray'>Elige la prueba y pulsa <b>Ejecutar análisis</b>. "
                 "Con <b>Automático</b>: 2 grupos → t de Welch; 3 o más → ANOVA + post hoc. "
                 "Si tus datos no son normales, usa Mann-Whitney o Kruskal-Wallis. "
                 "Los resultados se actualizan solos si cambias los datos.</p>"),
    "dos": ("<p style='color:gray'>Pega tus datos en <b>formato largo</b> (Factor A, Factor B, Valor) y pulsa "
            "<b>Ejecutar análisis</b>. El Factor A va en el eje X y el Factor B en la leyenda; "
            "puedes intercambiarlos en el panel derecho.</p>"),
}


class AnalysisPanel(QWidget):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.mode = "columnas"
        self._cfgs = {"columnas": AnalysisConfig(), "dos": AnalysisConfig(test=TESTS_TWO[0])}
        self._active = {"columnas": False, "dos": False}
        self._loading = False

        self.test = QComboBox()
        self.posthoc = QComboBox()
        self.control = QComboBox()
        self.compare = QComboBox(); self.compare.addItems(COMPARE_MODES)
        self.alpha = QComboBox(); self.alpha.addItems(ALPHAS)
        self.stars = QCheckBox("Mostrar asteriscos en el gráfico"); self.stars.setChecked(True)
        self.show_ns = QCheckBox("Incluir comparaciones no significativas (ns)")
        self.run_btn = QPushButton("Ejecutar análisis")
        self.out = QTextBrowser()

        self.box = box = QGroupBox("Configuración")
        f = QFormLayout(box)
        f.addRow("Prueba", self.test)
        f.addRow("Post hoc", self.posthoc)
        f.addRow("Grupo control", self.control)
        f.addRow("Comparar (2 factores)", self.compare)
        f.addRow("Alfa", self.alpha)
        f.addRow(self.stars)
        f.addRow(self.show_ns)
        row = QHBoxLayout(); row.addWidget(self.run_btn); row.addStretch()
        lay = QVBoxLayout(self)
        lay.addWidget(box); lay.addLayout(row); lay.addWidget(self.out, 1)

        self.run_btn.clicked.connect(self._run)
        self.test.currentTextChanged.connect(self._test_changed)
        for w in (self.posthoc, self.control, self.compare, self.alpha):
            w.currentTextChanged.connect(self._cfg_changed)
        for w in (self.stars, self.show_ns):
            w.toggled.connect(self._cfg_changed)
        self._load(self._cfgs[self.mode])

    # --- estado -----------------------------------------------------------
    def _tests(self) -> tuple[str, ...]:
        return TESTS_TWO if self.mode == "dos" else TESTS

    def _fill_posthoc(self, keep: str | None = None) -> None:
        choices = posthoc_choices(self.test.currentText())
        keep = keep if keep is not None else self.posthoc.currentText()
        self.posthoc.clear(); self.posthoc.addItems(choices)
        if keep in choices:
            self.posthoc.setCurrentText(keep)

    def _load(self, c: AnalysisConfig) -> None:
        self._loading = True
        self.test.clear(); self.test.addItems(self._tests())
        if c.test in self._tests():
            self.test.setCurrentText(c.test)
        self._fill_posthoc(c.posthoc)
        if c.control:
            self.control.setCurrentText(c.control)
        self.compare.setCurrentText(c.twoway_compare)
        self.alpha.setCurrentText(f"{c.alpha:.2f}")
        self.stars.setChecked(c.show_stars); self.show_ns.setChecked(c.show_ns)
        self._loading = False
        self._update_enabled()
        if not self._active[self.mode]:
            self.out.setHtml(PLACEHOLDERS[self.mode])

    def _update_enabled(self) -> None:
        self.posthoc.setEnabled(self.posthoc.count() > 0)
        self.control.setEnabled(self.mode == "columnas" and self.posthoc.currentText() == "Dunnett")
        self.compare.setEnabled(self.mode == "dos")

    def _run(self) -> None:
        if not self._has_analysis():
            return
        self._active[self.mode] = True
        self.changed.emit()

    def _test_changed(self, *_) -> None:
        if self._loading or not self._has_analysis():
            return
        self._fill_posthoc()
        self._update_enabled()
        if self._active[self.mode]:
            self.changed.emit()

    def _cfg_changed(self, *_) -> None:
        if self._loading or not self._has_analysis():
            return
        self._update_enabled()
        if self._active[self.mode]:
            self.changed.emit()

    # --- API --------------------------------------------------------------
    def _has_analysis(self, mode: str | None = None) -> bool:
        return (mode or self.mode) in self._cfgs

    def _apply_availability(self) -> None:
        ok = self._has_analysis()
        self.box.setEnabled(ok)
        self.run_btn.setEnabled(ok)
        if not ok:
            self.out.setHtml(NO_ANALYSIS)

    def set_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        if self._has_analysis():
            self._cfgs[self.mode] = self.get_config()
        self.mode = mode
        if self._has_analysis():
            self._load(self._cfgs[mode])
        self._apply_availability()
        self.changed.emit()

    def set_groups(self, names: list[str]) -> None:
        current = [self.control.itemText(i) for i in range(self.control.count())]
        if current == names:
            return
        keep = self.control.currentText()
        self._loading = True
        self.control.clear(); self.control.addItems(names)
        if keep in names:
            self.control.setCurrentText(keep)
        self._loading = False

    def get_config(self) -> AnalysisConfig:
        if not self._has_analysis():
            return AnalysisConfig(active=False)
        return AnalysisConfig(
            test=self.test.currentText(), posthoc=self.posthoc.currentText() or "Ninguno",
            control=self.control.currentText() or None, alpha=float(self.alpha.currentText()),
            show_stars=self.stars.isChecked(), show_ns=self.show_ns.isChecked(),
            active=self._active[self.mode], twoway_compare=self.compare.currentText())

    def get_configs(self) -> tuple[AnalysisConfig, AnalysisConfig]:
        if self._has_analysis():
            self._cfgs[self.mode] = self.get_config()
        return self._cfgs["columnas"], self._cfgs["dos"]

    def set_configs(self, cols: AnalysisConfig, dos: AnalysisConfig, mode: str | None = None) -> None:
        self._cfgs = {"columnas": cols, "dos": dos}
        self._active = {"columnas": cols.active, "dos": dos.active}
        if mode is not None:
            self.mode = mode
        if self._has_analysis():
            self._load(self._cfgs[self.mode])
        self._apply_availability()
        self.changed.emit()

    def show_html(self, body: str) -> None:
        self.out.setHtml(body)

    def show_error(self, msg: str) -> None:
        self.out.setHtml(f"<p style='color:#c0392b'><b>No se pudo analizar:</b> {html.escape(msg)}</p>")
