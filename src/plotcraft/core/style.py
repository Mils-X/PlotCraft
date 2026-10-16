from __future__ import annotations

from dataclasses import asdict, dataclass, fields

PALETTES = {
    "Gris": ["#BDBDBD"],
    "Clásica": ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860"],
    "Pastel": ["#A6CEE3", "#B2DF8A", "#FB9A99", "#FDBF6F", "#CAB2D6", "#FFFF99"],
    "Contraste": ["#1B1B1B", "#E69F00", "#56B4E9", "#009E73", "#D55E00", "#CC79A7"],
}


@dataclass
class PlotStyle:
    error_type: str = "SEM"
    palette: str = "Gris"
    title: str = ""
    xlabel: str = "Grupo"
    ylabel: str = "Valor"
    ymin: float | None = 0.0
    ymax: float | None = None
    show_points: bool = False
    font_size: int = 11
    label_rotation: str = "auto"  # "auto", "0", "45", "90"
    width: float = 6.0
    height: float = 4.5

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PlotStyle":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})
