from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget


class OptionalNumber(QWidget):
    """Número opcional: vacío = automático/libre (el texto lo da el marcador de posición)."""

    changed = Signal()

    def __init__(self, placeholder: str = "Auto") -> None:
        super().__init__()
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
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
