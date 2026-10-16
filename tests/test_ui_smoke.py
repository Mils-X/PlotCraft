import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from plotcraft.ui.main_window import MainWindow


def test_window_roundtrip():
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.sheet.set_data({"C-": [1.0, 2.0, 3.0], "T1": [4.0, 5.0, 6.0]})
    assert list(w.sheet.get_data()) == ["C-", "T1"]
    w.refresh_plot()
    assert len(w.canvas.figure.axes[0].patches) == 2
    st = w.props.get_style()
    w.props.set_style(st)
    assert w.props.get_style() == st
