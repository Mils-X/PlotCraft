"""Base común de las hojas de datos: copiar, cortar, pegar, borrar, columnas dinámicas y menús."""
from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence
from PySide6.QtWidgets import QInputDialog, QMenu, QTableWidget, QTableWidgetItem


def to_float(s: str) -> float | None:
    try:
        return float(s.strip().replace(",", "."))
    except ValueError:
        return None


def unique_names(names: list[str]) -> list[str]:
    """Evita que dos columnas con el mismo nombre se pisen entre sí."""
    seen: dict[str, int] = {}
    out = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n} ({seen[n]})")
    return out


def parse_clipboard(text: str) -> list[list[str]]:
    """Filas separadas por tabulador. Conserva las filas vacías intermedias (si no, los datos se
    recorrerían) y solo descarta las vacías del final."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return [ln.split("\t") for ln in lines]


class SheetBase(QTableWidget):
    data_changed = Signal()
    header_fmt = "Columna {}"   # nombre de las columnas nuevas
    first_insertable = 0        # primera posición donde se puede insertar una columna
    protected_cols: frozenset[int] = frozenset()   # columnas que no se pueden eliminar

    def __init__(self, rows: int, headers: list[str], growable: bool = False, text_cols: tuple[int, ...] = ()) -> None:
        super().__init__(rows, len(headers))
        self.growable = growable
        self.text_cols = set(text_cols)
        self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().sectionDoubleClicked.connect(self._rename)
        self.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(
            lambda pos: self._menu(self.horizontalHeader().mapToGlobal(pos), self.horizontalHeader().logicalIndexAt(pos)))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self._menu(self.viewport().mapToGlobal(pos), self.columnAt(pos.x())))
        self.itemChanged.connect(self._on_item_changed)

    # --- teclado -----------------------------------------------------------
    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.matches(QKeySequence.Copy):
            self.copy_selection()
        elif e.matches(QKeySequence.Cut):
            self.cut_selection()
        elif e.matches(QKeySequence.Paste):
            self.paste()
        elif e.key() == Qt.Key_Delete:
            self.clear_selection()
        else:
            super().keyPressEvent(e)

    # --- selección -----------------------------------------------------------
    def _bounds(self) -> tuple[int, int, int, int] | None:
        """(fila1, fila2, col1, col2) de la selección; si no hay, de la celda actual."""
        ranges = self.selectedRanges()
        if ranges:
            return (min(r.topRow() for r in ranges), max(r.bottomRow() for r in ranges),
                    min(r.leftColumn() for r in ranges), max(r.rightColumn() for r in ranges))
        if self.currentRow() >= 0 and self.currentColumn() >= 0:
            r, c = self.currentRow(), self.currentColumn()
            return r, r, c, c
        return None

    def _anchor(self) -> tuple[int, int]:
        """Esquina superior izquierda de la selección: donde empieza el pegado."""
        b = self._bounds()
        return (b[0], b[2]) if b else (0, 0)

    def _cell(self, r: int, c: int) -> str:
        it = self.item(r, c)
        return it.text() if it else ""

    # --- copiar / cortar / pegar / borrar -----------------------------------------
    def selection_text(self) -> str:
        b = self._bounds()
        if not b:
            return ""
        r1, r2, c1, c2 = b
        rows = [[self._cell(r, c) for c in range(c1, c2 + 1)] for r in range(r1, r2 + 1)]
        while len(rows) > 1 and not any(rows[-1]):   # sin filas vacías al final (columnas completas)
            rows.pop()
        return "\n".join("\t".join(r) for r in rows)

    def copy_selection(self) -> None:
        text = self.selection_text()
        if text:
            QGuiApplication.clipboard().setText(text)

    def cut_selection(self) -> None:
        self.copy_selection()
        self.clear_selection()

    def clear_selection(self) -> None:
        b = self._bounds()
        if not b:
            return
        r1, r2, c1, c2 = b
        with QSignalBlocker(self):
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    if self.item(r, c):
                        self.item(r, c).setText("")
        self.data_changed.emit()

    def _row_is_header(self, row: list[str], c0: int) -> bool:
        """Fila de títulos: todas sus celdas de columnas numéricas son texto (y hay al menos una)."""
        nums = [v.strip() for j, v in enumerate(row) if v.strip() and (c0 + j) not in self.text_cols]
        return bool(nums) and all(to_float(v) is None for v in nums)

    def paste(self) -> None:
        rows = parse_clipboard(QGuiApplication.clipboard().text())
        if not rows:
            return
        r0, c0 = self._anchor()          # se pega donde estás, también cuando hay fila de títulos
        has_header = len(rows) > 1 and self._row_is_header(rows[0], c0)
        with QSignalBlocker(self):
            self._ensure_cols(c0 + max(len(r) for r in rows))
            if has_header:
                for j, h in enumerate(rows[0]):
                    if c0 + j < self.columnCount() and h.strip():
                        self.horizontalHeaderItem(c0 + j).setText(h.strip())
                rows = rows[1:]
            while r0 + len(rows) > self.rowCount():
                self.insertRow(self.rowCount())
            for i, row in enumerate(rows):
                for j, cell in enumerate(row):
                    if c0 + j < self.columnCount():
                        self.setItem(r0 + i, c0 + j, QTableWidgetItem(cell.strip()))
        self._ensure_spare_column()
        self.data_changed.emit()

    # --- columnas ---------------------------------------------------------------
    def _header_names(self) -> set[str]:
        return {it.text() for c in range(self.columnCount()) if (it := self.horizontalHeaderItem(c))}

    def _next_index(self) -> int:
        return self.columnCount()      # XY: Y1 está en la columna 1; subclases pueden cambiarlo

    def _new_header(self) -> str:
        names = self._header_names()
        k = self._next_index()
        while self.header_fmt.format(k) in names:
            k += 1
        return self.header_fmt.format(k)

    def _ensure_cols(self, n: int) -> None:
        while self.growable and self.columnCount() < n:
            self.insert_column(self.columnCount())

    def _ensure_spare_column(self) -> None:
        """Siempre hay una columna vacía al final, para seguir agregando datos."""
        if not self.growable:
            return
        last = self.columnCount() - 1
        if any(self._cell(r, last).strip() for r in range(self.rowCount())):
            self.insert_column(self.columnCount())

    def insert_column(self, at: int) -> None:
        if not self.growable or at < self.first_insertable:
            return
        at = min(at, self.columnCount())
        name = self._new_header()      # antes de insertar: la columna nueva aún no tiene encabezado
        self.insertColumn(at)
        self.setHorizontalHeaderItem(at, QTableWidgetItem(name))

    def insert_column_right(self) -> None:
        b = self._bounds()
        self.insert_column((b[3] + 1) if b else self.columnCount())
        self.data_changed.emit()

    def delete_selected_columns(self) -> None:
        b = self._bounds()
        if not self.growable or not b:
            return
        cols = [c for c in range(b[3], b[2] - 1, -1) if c not in self.protected_cols]
        for c in cols:
            if self.columnCount() > 1:
                self.removeColumn(c)
        self._ensure_spare_column()
        self.data_changed.emit()

    def _on_item_changed(self, _item) -> None:
        self._ensure_spare_column()
        self.data_changed.emit()

    def _rename(self, col: int) -> None:
        cur = self.horizontalHeaderItem(col).text()
        text, ok = QInputDialog.getText(self, "Renombrar columna", "Nombre:", text=cur)
        if ok and text.strip():
            self.horizontalHeaderItem(col).setText(text.strip())
            self.data_changed.emit()

    def _menu(self, global_pos, col: int) -> None:
        menu = QMenu(self)
        menu.addAction("Copiar\tCtrl+C", self.copy_selection)
        menu.addAction("Cortar\tCtrl+X", self.cut_selection)
        menu.addAction("Pegar\tCtrl+V", self.paste)
        menu.addAction("Borrar contenido\tSupr", self.clear_selection)
        if 0 <= col < self.columnCount():
            menu.addSeparator()
            menu.addAction("Renombrar columna…", lambda: self._rename(col))
            if self.growable:
                left = menu.addAction("Insertar columna a la izquierda", lambda: (self.insert_column(col), self.data_changed.emit()))
                left.setEnabled(col >= self.first_insertable)
                menu.addAction("Insertar columna a la derecha", lambda: (self.insert_column(col + 1), self.data_changed.emit()))
                rm = menu.addAction("Eliminar columna(s) seleccionada(s)", self.delete_selected_columns)
                rm.setEnabled(col not in self.protected_cols)
        menu.exec(global_pos)
