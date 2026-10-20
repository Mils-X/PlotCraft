"""Punto de entrada: ``plotcraft [proyecto.pcft]``, ``plotcraft --install-launcher``."""
from __future__ import annotations

import argparse
import sys

from plotcraft import __version__


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="plotcraft", description="PlotCraft: gráficos científicos y estadística.")
    ap.add_argument("file", nargs="?", help="proyecto .pcft que se abre al iniciar")
    ap.add_argument("--version", action="version", version=f"PlotCraft {__version__}")
    ap.add_argument("--install-launcher", action="store_true",
                    help="agrega PlotCraft al menú de aplicaciones (con ícono y asociación de archivos .pcft)")
    ap.add_argument("--uninstall-launcher", action="store_true", help="quita el lanzador del menú de aplicaciones")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    args, qt_args = build_parser().parse_known_args(argv[1:])

    if args.install_launcher or args.uninstall_launcher:   # sin Qt: funciona también sin pantalla
        from plotcraft import launcher
        if args.install_launcher:
            made = launcher.install()
            print("Lanzador instalado:")
            for p in made.values():
                print(f"  {p}")
            print(f"Ejecuta con: {sys.executable} -m plotcraft")
            print("Busca «PlotCraft» en el menú de aplicaciones (puede requerir cerrar sesión la primera vez).")
            print("Si mueves esta carpeta, vuelve a ejecutar: plotcraft --install-launcher")
        else:
            gone = launcher.uninstall()
            print("Lanzador eliminado." if gone else "No había lanzador instalado.")
        return 0

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from plotcraft.launcher import RESOURCES
    from plotcraft.ui.main_window import MainWindow

    app = QApplication([argv[0]] + qt_args)
    app.setApplicationName("plotcraft")
    app.setApplicationDisplayName("PlotCraft")
    app.setDesktopFileName("plotcraft")            # el escritorio asocia la ventana con plotcraft.desktop
    app.setWindowIcon(QIcon(str(RESOURCES / "plotcraft.svg")))
    win = MainWindow()
    if args.file:
        win.open_path(args.file)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
