from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QInputDialog, QTableWidget, QTableWidgetItem

ROWS, COLS = 60, 8


def _is_number(s: str) -> bool:
    try:
        float(s.replace(",", "."))
        return True
    except ValueError:
        return False


class DataSheet(QTableWidget):
    """Tabla de columnas: cada columna es un grupo y cada fila una réplica."""

    data_changed = Signal()

    def __init__(self) -> None:
        super().__init__(ROWS, COLS)
        self._reset_headers()
        self.horizontalHeader().sectionDoubleClicked.connect(self._rename)
        self.itemChanged.connect(lambda _: self.data_changed.emit())
        QShortcut(QKeySequence.Paste, self, activated=self.paste)
        QShortcut(QKeySequence.Delete, self, activated=self._clear_selection)

    def _reset_headers(self) -> None:
        self.setHorizontalHeaderLabels([f"Grupo {i + 1}" for i in range(self.columnCount())])

    def _rename(self, col: int) -> None:
        cur = self.horizontalHeaderItem(col).text()
        text, ok = QInputDialog.getText(self, "Renombrar grupo", "Nombre:", text=cur)
        if ok and text.strip():
            self.horizontalHeaderItem(col).setText(text.strip())
            self.data_changed.emit()

    def _clear_selection(self) -> None:
        with QSignalBlocker(self):
            for it in self.selectedItems():
                it.setText("")
        self.data_changed.emit()

    def paste(self) -> None:
        text = QGuiApplication.clipboard().text()
        rows = [r.split("\t") for r in text.splitlines() if r.strip()]
        if not rows:
            return
        r0, c0 = max(self.currentRow(), 0), max(self.currentColumn(), 0)
        has_header = not any(_is_number(c) for c in rows[0] if c.strip()) and len(rows) > 1
        with QSignalBlocker(self):
            if has_header:
                r0 = 0
                c0 = 0 if self.currentColumn() < 0 else c0
                for j, h in enumerate(rows[0]):
                    self._ensure(r0, c0 + j)
                    self.horizontalHeaderItem(c0 + j).setText(h.strip() or f"Grupo {c0 + j + 1}")
                rows = rows[1:]
            for i, row in enumerate(rows):
                for j, cell in enumerate(row):
                    self._ensure(r0 + i, c0 + j)
                    self.setItem(r0 + i, c0 + j, QTableWidgetItem(cell.strip()))
        self.data_changed.emit()

    def _ensure(self, row: int, col: int) -> None:
        while row >= self.rowCount():
            self.insertRow(self.rowCount())
        while col >= self.columnCount():
            n = self.columnCount()
            self.insertColumn(n)
            self.setHorizontalHeaderItem(n, QTableWidgetItem(f"Grupo {n + 1}"))

    def get_data(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for c in range(self.columnCount()):
            vals = []
            for r in range(self.rowCount()):
                it = self.item(r, c)
                if it and _is_number(it.text().strip()):
                    vals.append(float(it.text().strip().replace(",", ".")))
            if vals:
                out[self.horizontalHeaderItem(c).text()] = vals
        return out

    def set_data(self, data: dict[str, list[float]]) -> None:
        with QSignalBlocker(self):
            self.clearContents()
            self.setRowCount(max(ROWS, max((len(v) for v in data.values()), default=0)))
            self.setColumnCount(max(COLS, len(data)))
            self._reset_headers()
            for c, (name, vals) in enumerate(data.items()):
                self.horizontalHeaderItem(c).setText(name)
                for r, v in enumerate(vals):
                    if not math.isnan(v):
                        self.setItem(r, c, QTableWidgetItem(f"{v:g}"))
        self.data_changed.emit()
