"""Hojas de datos para los diseños XY y burbujas."""
from __future__ import annotations

import math

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QTableWidgetItem

from plotcraft.core.xydata import BubbleData, XYData
from plotcraft.ui.sheet_base import SheetBase, to_float, unique_names  # noqa: F401 (to_float reexportado)


class GridSheet(SheetBase):
    """Tabla con encabezados editables; base de las hojas XY y burbujas."""

    def headers(self) -> list[str]:
        return [self.horizontalHeaderItem(c).text() for c in range(self.columnCount())]

    def rows_text(self) -> list[list[str]]:
        out = []
        for r in range(self.rowCount()):
            row = [self._cell(r, c).strip() for c in range(self.columnCount())]
            if any(row):
                out.append(row)
        return out

    def _fill(self, headers: list[str], rows: list[list[str]]) -> None:
        with QSignalBlocker(self):
            self.clearContents()
            if self.growable:
                self.setColumnCount(max(self.columnCount(), len(headers)))
            self.setRowCount(max(200, len(rows) + 20))
            for c in range(self.columnCount()):
                self.setHorizontalHeaderItem(c, QTableWidgetItem(headers[c] if c < len(headers) else self._new_header()))
            for r, row in enumerate(rows):
                for c, v in enumerate(row):
                    self.setItem(r, c, QTableWidgetItem(v))
        self._ensure_spare_column()
        self.data_changed.emit()


class XYSheet(GridSheet):
    """Columna X y tantas columnas Y (series) como quieras. Filas con el mismo X = réplicas."""

    header_fmt = "Y{}"
    first_insertable = 1                 # la columna X siempre queda primera
    protected_cols = frozenset({0})      # y no se puede eliminar

    def __init__(self) -> None:
        super().__init__(200, ["X", "Y1", "Y2", "Y3"], growable=True)

    def get_data(self) -> XYData:
        heads = unique_names(self.headers())
        xy = XYData(heads[0])
        cols: dict[str, list[float]] = {h: [] for h in heads[1:]}
        for row in self.rows_text():
            x = to_float(row[0])
            if x is None:
                continue
            xy.x.append(x)
            for j, h in enumerate(heads[1:], start=1):
                v = to_float(row[j]) if j < len(row) else None
                cols[h].append(math.nan if v is None else v)
        xy.series = {h: v for h, v in cols.items() if any(not math.isnan(t) for t in v)}
        return xy

    def set_data(self, xy: XYData) -> None:
        names = list(xy.series)
        rows = [[f"{x:g}"] + ["" if math.isnan(xy.series[n][i]) else f"{xy.series[n][i]:g}" for n in names]
                for i, x in enumerate(xy.x)]
        self._fill([xy.x_name] + names if names else ["X", "Y1", "Y2", "Y3"], rows)


class BubbleSheet(GridSheet):
    """X, Y, Tamaño y Grupo (opcional)."""

    def __init__(self) -> None:
        super().__init__(200, ["X", "Y", "Tamaño", "Grupo"], text_cols=(3,))

    def get_data(self) -> BubbleData:
        h = self.headers()
        bd = BubbleData(h[0], h[1], h[2], h[3])
        for row in self.rows_text():
            x, y, s = to_float(row[0]), to_float(row[1]), to_float(row[2])
            if x is None or y is None or s is None:
                continue
            bd.x.append(x); bd.y.append(y); bd.size.append(s); bd.group.append(row[3])
        return bd

    def set_data(self, bd: BubbleData) -> None:
        rows = [[f"{x:g}", f"{y:g}", f"{s:g}", g] for x, y, s, g in zip(bd.x, bd.y, bd.size, bd.group)]
        self._fill([bd.x_name, bd.y_name, bd.size_name, bd.group_name], rows)
