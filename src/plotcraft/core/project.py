"""Proyecto .pcft: un zip con project.json."""
from __future__ import annotations

import json
import math
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .style import PlotStyle

FORMAT_VERSION = 1


@dataclass
class Project:
    name: str = "Sin título"
    data: dict[str, list[float]] = field(default_factory=dict)
    style: PlotStyle = field(default_factory=PlotStyle)

    def to_dict(self) -> dict:
        return {
            "format_version": FORMAT_VERSION,
            "name": self.name,
            # NaN no es JSON válido: se guarda como null
            "data": {k: [None if math.isnan(v) else v for v in vals] for k, vals in self.data.items()},
            "style": self.style.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        if d.get("format_version", 1) > FORMAT_VERSION:
            raise ValueError("El proyecto fue creado con una versión más nueva de PlotCraft.")
        data = {k: [math.nan if v is None else float(v) for v in vals] for k, vals in d.get("data", {}).items()}
        return cls(d.get("name", "Sin título"), data, PlotStyle.from_dict(d.get("style", {})))

    def save(self, path: str | Path) -> None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("project.json", json.dumps(self.to_dict(), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        with zipfile.ZipFile(path) as z:
            return cls.from_dict(json.loads(z.read("project.json")))
