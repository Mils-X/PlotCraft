"""Proyecto .pcft: un zip con project.json."""
from __future__ import annotations

import json
import math
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .analysis import AnalysisConfig
from .fitting import FitConfig
from .style import PlotStyle
from .twoway import TwoWayData
from .xydata import BubbleData, XYData

FORMAT_VERSION = 5


@dataclass
class Project:
    name: str = "Sin título"
    data: dict[str, list[float]] = field(default_factory=dict)
    style: PlotStyle = field(default_factory=PlotStyle)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    mode: str = "columnas"  # "columnas", "dos" (2 factores), "xy" o "burbujas"
    twoway: TwoWayData = field(default_factory=TwoWayData)
    analysis_twoway: AnalysisConfig = field(default_factory=lambda: AnalysisConfig(test="ANOVA de dos vías"))
    xy: XYData = field(default_factory=XYData)
    bubble: BubbleData = field(default_factory=BubbleData)
    fit: FitConfig = field(default_factory=FitConfig)

    def to_dict(self) -> dict:
        return {
            "format_version": FORMAT_VERSION,
            "name": self.name,
            # NaN no es JSON válido: se guarda como null
            "data": {k: [None if math.isnan(v) else v for v in vals] for k, vals in self.data.items()},
            "style": self.style.to_dict(),
            "analysis": self.analysis.to_dict(),
            "mode": self.mode,
            "twoway": self.twoway.to_dict(),
            "analysis_twoway": self.analysis_twoway.to_dict(),
            "xy": self.xy.to_dict(),
            "bubble": self.bubble.to_dict(),
            "fit": self.fit.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        if d.get("format_version", 1) > FORMAT_VERSION:
            raise ValueError("El proyecto fue creado con una versión más nueva de PlotCraft.")
        data = {k: [math.nan if v is None else float(v) for v in vals] for k, vals in d.get("data", {}).items()}
        return cls(d.get("name", "Sin título"), data, PlotStyle.from_dict(d.get("style", {})),
                   AnalysisConfig.from_dict(d.get("analysis", {})),
                   d.get("mode", "columnas"),
                   TwoWayData.from_dict(d.get("twoway", {})),
                   AnalysisConfig.from_dict(d.get("analysis_twoway", {"test": "ANOVA de dos vías"})),
                   XYData.from_dict(d.get("xy", {})), BubbleData.from_dict(d.get("bubble", {})),
                   FitConfig.from_dict(d.get("fit", {})))

    def save(self, path: str | Path) -> None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("project.json", json.dumps(self.to_dict(), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        with zipfile.ZipFile(path) as z:
            return cls.from_dict(json.loads(z.read("project.json")))
