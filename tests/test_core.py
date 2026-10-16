import math

import numpy as np
import pytest
from scipy import stats

from plotcraft.core.plotting import make_bar_figure
from plotcraft.core.project import Project
from plotcraft.core.stats import summarize
from plotcraft.core.style import PlotStyle

VALS = [10.0, 12.0, 11.0, 13.0, 9.0]


def test_sd_sem_ci():
    sd = np.std(VALS, ddof=1)
    assert summarize(VALS, "SD").error == pytest.approx(sd)
    assert summarize(VALS, "SEM").error == pytest.approx(sd / math.sqrt(5))
    assert summarize(VALS, "IC95").error == pytest.approx(stats.t.ppf(0.975, 4) * sd / math.sqrt(5))
    assert summarize(VALS).mean == pytest.approx(11.0)


def test_edge_cases():
    assert summarize([]).n == 0
    assert summarize([5.0]).error == 0.0
    assert summarize([1.0, math.nan, 3.0]).n == 2
    with pytest.raises(ValueError):
        summarize(VALS, "XX")


def test_project_roundtrip(tmp_path):
    p = Project("t", {"C-": [1.0, math.nan, 3.0], "T1": [4.0]}, PlotStyle(title="Hola", ymax=100.0))
    f = tmp_path / "a.pcft"
    p.save(f)
    q = Project.load(f)
    assert q.style.title == "Hola" and q.style.ymax == 100.0
    assert q.data["T1"] == [4.0] and math.isnan(q.data["C-"][1])


def test_figure_builds_and_rotates_long_labels():
    data = {"Control_Negativo": VALS, "Control_Positivo": VALS, "Tratamiento_T1": VALS,
            "Tratamiento_T2": VALS, "Tratamiento_T3": VALS}
    fig = make_bar_figure(data, PlotStyle(show_points=True))
    labels = fig.axes[0].get_xticklabels()
    assert len(labels) == 5 and labels[0].get_rotation() == 45
    short = make_bar_figure({"C-": VALS, "T1": VALS}, PlotStyle())
    assert short.axes[0].get_xticklabels()[0].get_rotation() == 0


def test_empty_data():
    assert make_bar_figure({}, PlotStyle()) is not None
