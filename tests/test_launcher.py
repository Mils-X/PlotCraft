import os
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from plotcraft import __version__, launcher
from plotcraft.core.project import Project


def parse_desktop(text: str) -> dict[str, str]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines[0] == "[Desktop Entry]"
    out = {}
    for ln in lines[1:]:
        assert not ln.startswith("[")                      # una sola sección
        k, _, v = ln.partition("=")
        assert k and k not in out                          # claves únicas
        out[k] = v
    return out


def exec_argv(value: str) -> list[str]:
    """Interpreta el campo Exec como lo hace un escritorio (comillas y escapes de la especificación)."""
    args, cur, inq, i = [], "", False, 0
    while i < len(value):
        c = value[i]
        if inq and c == "\\" and i + 1 < len(value):
            cur += value[i + 1]; i += 2; continue
        if c == '"':
            inq = not inq
        elif c == " " and not inq:
            args.append(cur); cur = ""
        else:
            cur += c
        i += 1
    return args + [cur]


# ---------- contenido del .desktop ----------
def test_desktop_entry_has_required_keys_and_valid_values():
    d = parse_desktop(launcher.desktop_entry("/usr/bin/python3"))
    assert {"Type", "Name", "Exec", "Icon", "Categories", "MimeType"} <= set(d)
    assert d["Type"] == "Application" and d["Name"] == "PlotCraft" and d["Terminal"] == "false"
    assert d["Exec"] == "/usr/bin/python3 -m plotcraft %f" and d["Icon"] == "plotcraft"
    assert d["Categories"].endswith(";") and d["MimeType"] == "application/x-plotcraft;" and d["Keywords"].endswith(";")
    assert set(d["Categories"].strip(";").split(";")) <= {"Science", "Education", "DataVisualization"}   # categorías registradas


@pytest.mark.parametrize("python", ["/home/milton/mi carpeta/.venv/bin/python", "/opt/a&b/py", '/x/"q"/py', "/x/$HOME/py", "/x/100%/py"])
def test_exec_quoting_survives_special_characters(python):
    argv = exec_argv(launcher.exec_quote(python) + " -m plotcraft %f")
    assert argv[0] == python.replace("%", "%%") and argv[1:] == ["-m", "plotcraft", "%f"]


# ---------- instalación / desinstalación ----------
def test_install_creates_files_and_uninstall_removes_them(tmp_path):
    out = launcher.install(python=sys.executable, home=tmp_path, refresh=False)
    assert set(out) == {"desktop", "icon_svg", "icon_png", "mime"} and all(p.exists() for p in out.values())
    assert out["desktop"].parent == tmp_path / "applications" and os.access(out["desktop"], os.X_OK)
    exec_ = exec_argv(parse_desktop(out["desktop"].read_text(encoding="utf-8"))["Exec"])
    assert Path(exec_[0]).is_file() and exec_[1:3] == ["-m", "plotcraft"]
    launcher.install(python=sys.executable, home=tmp_path, refresh=False)       # reinstalar es idempotente
    removed = launcher.uninstall(home=tmp_path, refresh=False)
    assert len(removed) == 4 and not any(p.exists() for p in out.values())
    assert launcher.uninstall(home=tmp_path, refresh=False) == []


def test_data_home_follows_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "datos"))
    assert launcher.data_home() == tmp_path / "datos"
    monkeypatch.delenv("XDG_DATA_HOME")
    assert launcher.data_home() == Path.home() / ".local" / "share"


def test_icons_are_valid_files():
    root = ET.parse(launcher.RESOURCES / "plotcraft.svg").getroot()
    assert root.tag.endswith("svg") and root.get("viewBox") == "0 0 256 256"
    png = (launcher.RESOURCES / "plotcraft.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (256, 256)


@pytest.mark.skipif(not shutil.which("update-mime-database"), reason="update-mime-database no disponible")
def test_system_mime_tool_accepts_our_xml_and_registers_pcft(tmp_path):
    launcher.install(python=sys.executable, home=tmp_path, refresh=False)
    r = subprocess.run(["update-mime-database", str(tmp_path / "mime")], capture_output=True, text=True)
    # éxito; lo único tolerado es el aviso de que el directorio temporal no está en XDG_DATA_DIRS
    assert r.returncode == 0 and (not r.stderr.strip() or "search path" in r.stderr)
    assert "rror" not in r.stderr and "nvalid" not in r.stderr
    assert "application/x-plotcraft:*.pcft" in (tmp_path / "mime" / "globs2").read_text()
    assert "application/x-plotcraft application/zip" in (tmp_path / "mime" / "subclasses").read_text()
    # tras desinstalar y actualizar, desaparece
    launcher.uninstall(home=tmp_path, refresh=False)
    subprocess.run(["update-mime-database", str(tmp_path / "mime")], check=True, capture_output=True)
    assert "plotcraft" not in (tmp_path / "mime" / "globs2").read_text()


# ---------- línea de comandos ----------
def run_cli(*args, env=None, timeout=60):
    e = {**os.environ, "QT_QPA_PLATFORM": "offscreen", **(env or {})}
    return subprocess.run([sys.executable, "-m", "plotcraft", *args], capture_output=True, text=True, env=e, timeout=timeout)


def test_cli_version_and_launcher_roundtrip(tmp_path):
    r = run_cli("--version")
    assert r.returncode == 0 and __version__ in r.stdout
    env = {"XDG_DATA_HOME": str(tmp_path)}
    r = run_cli("--install-launcher", env=env)
    assert r.returncode == 0 and "Lanzador instalado" in r.stdout
    assert (tmp_path / "applications" / "plotcraft.desktop").exists() and (tmp_path / "mime" / "globs2").exists()
    r = run_cli("--uninstall-launcher", env=env)
    assert r.returncode == 0 and "eliminado" in r.stdout and not (tmp_path / "applications" / "plotcraft.desktop").exists()
    assert "No había" in run_cli("--uninstall-launcher", env=env).stdout


def test_app_starts_with_a_project_file_argument(tmp_path):
    f = tmp_path / "demo.pcft"
    Project("demo", {"A": [1.0, 2.0, 3.0], "B": [4.0, 5.0, 6.0]}).save(f)
    e = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    proc = subprocess.Popen([sys.executable, "-m", "plotcraft", str(f)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=e)
    try:
        proc.wait(timeout=6)
        pytest.fail("la aplicación debía quedar abierta")
    except subprocess.TimeoutExpired:
        pass                                                        # sigue corriendo = arrancó bien
    finally:
        proc.kill()
        _, err = proc.communicate()
    assert "Traceback" not in err


def test_open_path_handles_good_and_bad_files(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox
    from plotcraft.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))
    w = MainWindow()
    good = tmp_path / "ok.pcft"
    Project("ok", {"A": [1.0, 2.0], "B": [3.0, 4.0]}).save(good)
    assert w.open_path(str(good)) and set(w.sheet.get_data()) == {"A", "B"} and w.windowTitle().endswith("ok.pcft")
    bad = tmp_path / "mal.pcft"
    bad.write_text("no soy un zip")
    assert w.open_path(str(bad)) is False and shown and "mal.pcft" in shown[0]
    assert w.open_path(str(tmp_path / "no_existe.pcft")) is False
