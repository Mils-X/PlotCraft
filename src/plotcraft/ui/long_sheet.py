from __future__ import annotations

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QTableWidgetItem

from plotcraft.core.twoway import TwoWayData
from plotcraft.ui.sheet_base import SheetBase, to_float

ROWS = 200
DEFAULT_HEADERS = ["Factor A", "Factor B", "Valor"]


class LongSheet(SheetBase):
    """Formato largo para 2 factores: una fila por observación (Factor A, Factor B, Valor)."""

    def __init__(self) -> None:
        super().__init__(ROWS, DEFAULT_HEADERS, text_cols=(0, 1))   # A y B son etiquetas; Valor es numérico

    def get_data(self) -> TwoWayData:
        h = [self.horizontalHeaderItem(c).text() for c in range(3)]
        td = TwoWayData(h[0], h[1], h[2])
        for r in range(self.rowCount()):
            a, b, y = (self._cell(r, c).strip() for c in range(3))
            v = to_float(y)
            if a and b and v is not None:
                td.a.append(a); td.b.append(b); td.y.append(v)
        return td

    def set_data(self, td: TwoWayData) -> None:
        with QSignalBlocker(self):
            self.clearContents()
            self.setRowCount(max(ROWS, len(td.y) + 20))
            for c, name in enumerate((td.a_name, td.b_name, td.y_name)):
                self.horizontalHeaderItem(c).setText(name)
            for r, (a, b, y) in enumerate(zip(td.a, td.b, td.y)):
                self.setItem(r, 0, QTableWidgetItem(a))
                self.setItem(r, 1, QTableWidgetItem(b))
                self.setItem(r, 2, QTableWidgetItem(f"{y:g}"))
        self.data_changed.emit()
