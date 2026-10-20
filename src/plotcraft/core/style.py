from __future__ import annotations

from dataclasses import asdict, dataclass, fields

PALETTES = {
    "Gris": ["#BDBDBD"],
    "Clásica": ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860"],
    "Pastel": ["#A6CEE3", "#B2DF8A", "#FB9A99", "#FDBF6F", "#CAB2D6", "#FFFF99"],
    "Contraste": ["#1B1B1B", "#E69F00", "#56B4E9", "#009E73", "#D55E00", "#CC79A7"],
}


WHISKERS = ("1.5 × RIQ", "Mín–Máx")

# Tipos de gráfico disponibles según el diseño de datos
CHARTS = {
    "columnas": ("Barras", "Cajas y bigotes", "Histograma"),
    "dos": ("Barras agrupadas", "Cajas agrupadas"),
    "xy": ("Dispersión", "Líneas y puntos", "Líneas", "Dosis-respuesta (4PL)"),
    "burbujas": ("Burbujas",),
}
DOSE_RESPONSE = "Dosis-respuesta (4PL)"
_XY = {"Dispersión", "Líneas y puntos", "Líneas", DOSE_RESPONSE}
# En qué gráficos tiene sentido cada opción del panel (para mostrar solo las relevantes)
OPTION_CHARTS = {
    "error": {"Barras", "Barras agrupadas", "Líneas y puntos", "Líneas", DOSE_RESPONSE},
    "points": {"Barras", "Barras agrupadas", "Cajas y bigotes", "Cajas agrupadas"},
    "swap": {"Barras agrupadas", "Cajas agrupadas"},
    "whisker": {"Cajas y bigotes", "Cajas agrupadas"},
    "bins": {"Histograma"},
    "density": {"Histograma"},
    "marker": {"Dispersión", "Líneas y puntos", DOSE_RESPONSE},
    "line_width": {"Líneas y puntos", "Líneas", DOSE_RESPONSE},
    "average": {"Líneas y puntos", "Líneas"},
    "trend": {"Dispersión"},
    "x_log": _XY | {"Burbujas"},
    "y_log": _XY | {"Burbujas"},
    "bubble": {"Burbujas"},
}


@dataclass
class PlotStyle:
    chart: str = "Barras"
    error_type: str = "SEM"
    palette: str = "Gris"
    title: str = ""
    xlabel: str = ""   # vacío = automático (nombre de la columna o del gráfico)
    ylabel: str = ""
    ymin: float | None = None  # None = automático (las barras parten de 0)
    ymax: float | None = None
    show_points: bool = False
    font_size: int = 11
    swap_factors: bool = False  # solo 2 factores: intercambia eje X y leyenda
    label_rotation: str = "auto"  # "auto", "0", "45", "90"
    whisker: str = WHISKERS[0]
    bins: int = 0               # 0 = automático
    density: bool = False
    marker_size: float = 6.0
    line_width: float = 1.8
    average_reps: bool = True   # promediar réplicas con el mismo X (líneas)
    trendline: bool = False
    x_log: bool = False
    y_log: bool = False
    bubble_scale: float = 1.0
    width: float = 6.0
    height: float = 4.5

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PlotStyle":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})
