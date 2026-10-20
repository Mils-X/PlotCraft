from __future__ import annotations

import math

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QTableWidgetItem

from plotcraft.ui.sheet_base import SheetBase, to_float, unique_names

ROWS, COLS = 60, 8


def _is_number(s: str) -> bool:
    return to_float(s) is not None


class DataSheet(SheetBase):
    """Tabla de columnas: cada columna es un grupo y cada fila una réplica."""

    header_fmt = "Grupo {}"

    def __init__(self) -> None:
        super().__init__(ROWS, [f"Grupo {i + 1}" for i in range(COLS)], growable=True)

    def _next_index(self) -> int:
        return self.columnCount() + 1     # "Grupo 1" es la primera columna

    def headers(self) -> list[str]:
        return [self.horizontalHeaderItem(c).text() for c in range(self.columnCount())]

    def get_data(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for name, c in zip(unique_names(self.headers()), range(self.columnCount())):
            vals = []
            for r in range(self.rowCount()):
                it = self.item(r, c)
                v = to_float(it.text()) if it else None
                if v is not None:
                    vals.append(v)
            if vals:
                out[name] = vals
        return out

    def set_data(self, data: dict[str, list[float]]) -> None:
        with QSignalBlocker(self):
            self.clearContents()
            self.setRowCount(max(ROWS, max((len(v) for v in data.values()), default=0) + 10))
            self.setColumnCount(max(COLS, len(data)))
            for c in range(self.columnCount()):
                self.setHorizontalHeaderItem(c, QTableWidgetItem(f"Grupo {c + 1}"))
            for c, (name, vals) in enumerate(data.items()):
                self.horizontalHeaderItem(c).setText(name)
                for r, v in enumerate(vals):
                    if not math.isnan(v):
                        self.setItem(r, c, QTableWidgetItem(f"{v:g}"))
        self._ensure_spare_column()
        self.data_changed.emit()
