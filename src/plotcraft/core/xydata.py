"""Datos para los diseños XY y burbujas."""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


@dataclass
class XYData:
    """Una columna X y una o varias series Y alineadas por fila (NaN = vacío)."""
    x_name: str = "X"
    x: list[float] = field(default_factory=list)
    series: dict[str, list[float]] = field(default_factory=dict)

    def points(self, name: str) -> list[tuple[float, float]]:
        return [(x, y) for x, y in zip(self.x, self.series[name]) if not math.isnan(y)]

    def to_dict(self) -> dict:
        return {"x_name": self.x_name, "x": list(self.x),
                "series": {k: [_num(v) for v in vals] for k, vals in self.series.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "XYData":
        return cls(d.get("x_name", "X"), [float(v) for v in d.get("x", [])],
                   {k: [math.nan if v is None else float(v) for v in vals]
                    for k, vals in d.get("series", {}).items()})


@dataclass
class BubbleData:
    x_name: str = "X"
    y_name: str = "Y"
    size_name: str = "Tamaño"
    group_name: str = "Grupo"
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    size: list[float] = field(default_factory=list)
    group: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"x_name": self.x_name, "y_name": self.y_name, "size_name": self.size_name,
                "group_name": self.group_name, "x": list(self.x), "y": list(self.y),
                "size": list(self.size), "group": list(self.group)}

    @classmethod
    def from_dict(cls, d: dict) -> "BubbleData":
        return cls(d.get("x_name", "X"), d.get("y_name", "Y"), d.get("size_name", "Tamaño"),
                   d.get("group_name", "Grupo"), [float(v) for v in d.get("x", [])],
                   [float(v) for v in d.get("y", [])], [float(v) for v in d.get("size", [])],
                   [str(v) for v in d.get("group", [])])
