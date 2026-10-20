"""Lanzador para escritorios Linux (freedesktop): entrada en el menú, ícono y asociación de archivos .pcft.

No usa Qt, así que también funciona sin pantalla. Todo se instala en el directorio del usuario
(~/.local/share), sin permisos de administrador. Para quitarlo: ``plotcraft --uninstall-launcher``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_ID = "plotcraft"
MIME_TYPE = "application/x-plotcraft"
RESOURCES = Path(__file__).parent / "resources"

MIME_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="{MIME_TYPE}">
    <comment>Proyecto de PlotCraft</comment>
    <comment xml:lang="es">Proyecto de PlotCraft</comment>
    <icon name="{APP_ID}"/>
    <sub-class-of type="application/zip"/>
    <glob pattern="*.pcft"/>
  </mime-type>
</mime-info>
"""


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def exec_quote(arg: str) -> str:
    """Cita un argumento del campo Exec según la especificación Desktop Entry."""
    arg = arg.replace("%", "%%")
    if any(c in arg for c in ' \t\n"\'\\><~|&;$*?#()`'):
        for ch in ('\\', '"', '`', '$'):
            arg = arg.replace(ch, "\\" + ch)
        return f'"{arg}"'
    return arg


def desktop_entry(python: str) -> str:
    """Contenido del .desktop. Se ejecuta con el Python del entorno virtual: no hay que activarlo."""
    return "\n".join([
        "[Desktop Entry]",
        "Version=1.0",
        "Type=Application",
        "Name=PlotCraft",
        "GenericName=Gráficos científicos y estadística",
        "Comment=Gráficos, ANOVA, pruebas no paramétricas y curvas dosis-respuesta (IC50)",
        f"Exec={exec_quote(python)} -m plotcraft %f",
        f"Icon={APP_ID}",
        "Terminal=false",
        "StartupNotify=true",
        f"StartupWMClass={APP_ID}",
        "Categories=Science;Education;DataVisualization;",
        f"MimeType={MIME_TYPE};",
        "Keywords=gráficos;estadística;ANOVA;IC50;dosis-respuesta;Prism;",
        "",
    ])


def paths(home: Path | None = None) -> dict[str, Path]:
    h = home or data_home()
    return {
        "desktop": h / "applications" / f"{APP_ID}.desktop",
        "icon_svg": h / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg",
        "icon_png": h / "icons" / "hicolor" / "256x256" / "apps" / f"{APP_ID}.png",
        "mime": h / "mime" / "packages" / f"{APP_ID}.xml",
    }


def _refresh_caches(home: Path) -> list[str]:
    """Actualiza las cachés del escritorio si las herramientas existen; nunca falla."""
    done = []
    cmds = [("update-desktop-database", [str(home / "applications")]),
            ("update-mime-database", [str(home / "mime")]),
            ("gtk-update-icon-cache", ["-f", "-t", str(home / "icons" / "hicolor")])]
    for tool, args in cmds:
        exe = shutil.which(tool)
        if exe and Path(args[-1]).exists():
            try:
                subprocess.run([exe, *args], check=False, capture_output=True, timeout=30)
                done.append(tool)
            except (OSError, subprocess.SubprocessError):
                pass
    return done


def install(python: str | None = None, home: Path | None = None, refresh: bool = True) -> dict[str, Path]:
    """Instala el lanzador y devuelve las rutas creadas."""
    home = home or data_home()
    python = python or sys.executable
    out = paths(home)
    for p in out.values():
        p.parent.mkdir(parents=True, exist_ok=True)
    out["desktop"].write_text(desktop_entry(python), encoding="utf-8")
    out["desktop"].chmod(0o755)
    shutil.copyfile(RESOURCES / "plotcraft.svg", out["icon_svg"])
    shutil.copyfile(RESOURCES / "plotcraft.png", out["icon_png"])
    out["mime"].write_text(MIME_XML, encoding="utf-8")
    if refresh:
        _refresh_caches(home)
    return out


def uninstall(home: Path | None = None, refresh: bool = True) -> list[Path]:
    """Quita lo que instaló ``install``. Devuelve los archivos eliminados."""
    home = home or data_home()
    removed = []
    for p in paths(home).values():
        if p.exists():
            p.unlink()
            removed.append(p)
    if refresh:
        _refresh_caches(home)
    return removed
