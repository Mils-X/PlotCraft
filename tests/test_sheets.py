import math

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableWidgetItem, QTableWidgetSelectionRange

from plotcraft.ui.data_sheet import DataSheet
from plotcraft.ui.grid_sheet import BubbleSheet, XYSheet
from plotcraft.ui.long_sheet import LongSheet

app = QApplication.instance() or QApplication([])


def clip(text):
    QGuiApplication.clipboard().setText(text)


def col(sheet, c, n=6):
    return [sheet._cell(r, c) for r in range(n)]


def select(sheet, r1, r2, c1, c2):
    """Selecciona un rango (setCurrentCell reduce la selección a 1 celda, por eso se limpia después)."""
    sheet.setCurrentCell(r1, c1)
    sheet.clearSelection()
    sheet.setRangeSelected(QTableWidgetSelectionRange(r1, c1, r2, c2), True)


def fill(sheet, rows, c0=0):
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            sheet.setItem(i, c0 + j, QTableWidgetItem(v))


# ---------- bug 1: no se podían agregar columnas Y ----------
def test_xy_columns_grow_when_typing_in_last_column():
    s = XYSheet()
    assert s.columnCount() == 4
    s.setItem(0, 3, QTableWidgetItem("5"))           # escribir en la última columna crea otra
    assert s.columnCount() == 5 and s.horizontalHeaderItem(4).text() == "Y4"
    for _ in range(6):                                # y se puede seguir sin límite
        s.setItem(0, s.columnCount() - 1, QTableWidgetItem("1"))
    assert s.columnCount() == 11
    names = [s.horizontalHeaderItem(c).text() for c in range(s.columnCount())]
    assert len(set(names)) == len(names)


def test_xy_insert_and_delete_columns_x_is_protected():
    s = XYSheet()
    s.setCurrentCell(0, 1)
    s.insert_column_right()
    assert s.columnCount() == 5
    s.insert_column(0)                                # antes de X: no permitido
    assert s.columnCount() == 5 and s.horizontalHeaderItem(0).text() == "X"
    select(s, 0, 3, 0, 0)
    s.delete_selected_columns()                       # X no se elimina
    assert s.horizontalHeaderItem(0).text() == "X" and s.columnCount() == 5
    select(s, 0, 0, 0, 2)                             # X..Y4 seleccionadas: solo se eliminan las que no son X
    s.delete_selected_columns()
    assert s.horizontalHeaderItem(0).text() == "X" and s.columnCount() == 3
    assert [s.horizontalHeaderItem(c).text() for c in range(3)] == ["X", "Y2", "Y3"]
    select(s, 0, 0, 2, 2)
    s.delete_selected_columns()
    assert [s.horizontalHeaderItem(c).text() for c in range(s.columnCount())] == ["X", "Y2"]


def test_xy_many_series_reach_the_data():
    s = XYSheet()
    clip("Dosis\t" + "\t".join(f"S{i}" for i in range(1, 9)) + "\n1\t" + "\t".join(["5"] * 8) + "\n2\t" + "\t".join(["6"] * 8))
    s.paste()
    xy = s.get_data()
    assert xy.x == [1.0, 2.0] and list(xy.series) == [f"S{i}" for i in range(1, 9)]
    assert s.columnCount() == 10                      # 9 con datos + 1 libre al final


def test_data_sheet_also_grows_beyond_eight_groups():
    s = DataSheet()
    assert s.columnCount() == 8
    s.setItem(0, 7, QTableWidgetItem("1"))
    assert s.columnCount() == 9 and s.horizontalHeaderItem(8).text() == "Grupo 9"


# ---------- bug 2: se pegaba siempre en la primera columna ----------
def test_paste_column_with_header_lands_where_you_are():
    s = XYSheet()
    fill(s, [["1", "10"], ["2", "20"], ["3", "30"]])           # X y Y1 ya tienen datos
    s.setCurrentCell(0, 2)
    clip("Línea B\n100\n200\n300")
    s.paste()
    assert s.horizontalHeaderItem(2).text() == "Línea B"
    assert col(s, 2, 3) == ["100", "200", "300"]
    assert col(s, 0, 3) == ["1", "2", "3"] and col(s, 1, 3) == ["10", "20", "30"]   # nada se pisó
    xy = s.get_data()
    assert xy.series["Línea B"] == [100.0, 200.0, 300.0] and xy.series["Y1"] == [10.0, 20.0, 30.0]


def test_paste_after_selecting_a_whole_column_by_its_header():
    s = XYSheet()
    s.selectColumn(3)
    clip("Línea C\n7\n8")
    s.paste()
    assert s.horizontalHeaderItem(3).text() == "Línea C" and col(s, 3, 2) == ["7", "8"] and col(s, 0, 2) == ["", ""]


def test_paste_with_header_respects_row_and_data_sheet_and_long_sheet():
    s = XYSheet()
    s.setCurrentCell(5, 1)
    clip("Serie\n1\n2")
    s.paste()
    assert col(s, 1, 8) == ["", "", "", "", "", "1", "2", ""] and s.horizontalHeaderItem(1).text() == "Serie"
    d = DataSheet()
    d.setCurrentCell(0, 2)
    clip("Droga B\n4\n5\n6")
    d.paste()
    assert d.horizontalHeaderItem(2).text() == "Droga B" and col(d, 2, 3) == ["4", "5", "6"] and col(d, 0, 3) == ["", "", ""]
    lg = LongSheet()
    lg.setCurrentCell(0, 2)
    clip("Viabilidad\n10\n12")
    lg.paste()
    assert lg.horizontalHeaderItem(2).text() == "Viabilidad" and col(lg, 2, 2) == ["10", "12"] and col(lg, 0, 2) == ["", ""]


def test_paste_keeps_blank_rows_so_data_stays_aligned():
    s = XYSheet()
    clip("1\n\n3\n\n\n6\n\n")
    s.setCurrentCell(0, 1)
    s.paste()
    assert col(s, 1, 6) == ["1", "", "3", "", "", "6"]


def test_headerless_numeric_paste_is_not_taken_as_header():
    s = XYSheet()
    s.setCurrentCell(0, 2)
    clip("1\n2\n3")
    s.paste()
    assert s.horizontalHeaderItem(2).text() == "Y2" and col(s, 2, 3) == ["1", "2", "3"]


# ---------- bug 3: no se podía cortar (ni copiar) ----------
def test_ctrl_c_ctrl_x_ctrl_v_and_delete_on_keyboard():
    s = XYSheet()
    fill(s, [["1", "10", "11"], ["2", "20", "21"], ["3", "30", "31"]])
    select(s, 0, 2, 1, 2)
    clip("")
    QTest.keyClick(s, Qt.Key_C, Qt.ControlModifier)                   # copiar
    assert QGuiApplication.clipboard().text() == "10\t11\n20\t21\n30\t31"
    assert col(s, 1, 3) == ["10", "20", "30"]                         # copiar no borra
    QTest.keyClick(s, Qt.Key_X, Qt.ControlModifier)                   # cortar
    assert col(s, 1, 3) == ["", "", ""] and col(s, 2, 3) == ["", "", ""]
    assert col(s, 0, 3) == ["1", "2", "3"]                            # no toca lo no seleccionado
    select(s, 0, 0, 3, 3)                                             # última columna existente
    QTest.keyClick(s, Qt.Key_V, Qt.ControlModifier)                   # pegar 2 columnas: la hoja crece
    assert col(s, 3, 3) == ["10", "20", "30"] and col(s, 4, 3) == ["11", "21", "31"]
    assert s.columnCount() == 6                                       # y deja una libre al final
    select(s, 0, 0, 3, 3)
    QTest.keyClick(s, Qt.Key_Delete)
    assert s._cell(0, 3) == "" and s._cell(1, 3) == "20"


def test_cut_notifies_and_updates_data():
    s = XYSheet()
    fill(s, [["1", "10"], ["2", "20"]])
    seen = []
    s.data_changed.connect(lambda: seen.append(1))
    select(s, 0, 1, 1, 1)
    s.cut_selection()
    assert seen and "Y1" not in s.get_data().series and QGuiApplication.clipboard().text() == "10\n20"


def test_copy_whole_column_trims_trailing_empty_rows_and_roundtrips():
    d = DataSheet()
    fill(d, [["1", "5"], ["2", "6"], ["3", "7"]])
    d.selectColumn(1)
    d.copy_selection()
    assert QGuiApplication.clipboard().text() == "5\n6\n7"
    d.clearSelection(); d.setCurrentCell(0, 3)
    d.paste()
    assert col(d, 3, 3) == ["5", "6", "7"]


# ---------- otros ----------
def test_data_sheet_duplicate_names_do_not_overwrite():
    d = DataSheet()
    d.horizontalHeaderItem(0).setText("A"); d.horizontalHeaderItem(1).setText("A")
    fill(d, [["1", "9"], ["2", "8"]])
    assert d.get_data() == {"A": [1.0, 2.0], "A (2)": [9.0, 8.0]}


def test_bubble_sheet_is_fixed_but_copy_paste_work():
    b = BubbleSheet()
    assert not b.growable and b.columnCount() == 4
    clip("1\t2\t3\tA")
    b.setCurrentCell(0, 0)
    b.paste()
    b.insert_column(1)
    assert b.columnCount() == 4 and b.get_data().group == ["A"]


def test_edit_menu_acts_on_visible_sheet():
    from plotcraft.ui.main_window import MainWindow
    w = MainWindow()
    w.design.setCurrentIndex(2)
    w.tabs.setCurrentWidget(w.stack)
    w.xy_sheet.setCurrentCell(0, 1)
    w._update_edit_menu()
    assert w._edit_actions["insert"].isEnabled()
    w._edit_actions["insert"].trigger()
    assert w.xy_sheet.columnCount() == 5
    w.design.setCurrentIndex(3)
    w._update_edit_menu()
    assert not w._edit_actions["insert"].isEnabled() and w._edit_actions["paste"].isEnabled()
    w.tabs.setCurrentWidget(w.canvas)
    w._update_edit_menu()
    assert not w._edit_actions["paste"].isEnabled()
