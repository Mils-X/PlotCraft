import math

import numpy as np
import pytest

from plotcraft.core.fitting import FitConfig, fit_dose_response, fit_to_html, fit_xy, model
from plotcraft.core.xydata import XYData

DOSES = np.repeat([0.01, 0.1, 1, 10, 100, 1000], 3).astype(float)


def synth(bottom=5.0, top=100.0, ic50=3.0, hill=-1.2, sd=2.0, seed=0, doses=DOSES):
    rng = np.random.default_rng(seed)
    return doses, model(doses, bottom, top, math.log10(ic50), hill) + rng.normal(0, sd, len(doses))


# ---------- el modelo ----------
def test_model_hits_midpoint_and_asymptotes_with_prism_convention():
    assert model(3.0, 5, 100, math.log10(3.0), -1.2) == pytest.approx(52.5)          # a mitad de camino
    assert model(1e-6, 5, 100, 0.5, -1.2) == pytest.approx(100, abs=1e-3)            # decreciente: Top a dosis baja
    assert model(1e6, 5, 100, 0.5, -1.2) == pytest.approx(5, abs=1e-3)
    assert model(1e6, 5, 100, 0.5, +1.2) == pytest.approx(100, abs=1e-3)             # creciente: Top a dosis alta
    assert np.all(np.isfinite(model([1e-300, 1e300], 0, 1, 0, 30)))                  # sin desbordes


# ---------- contra una implementación independiente (lmfit) ----------
@pytest.mark.parametrize("seed,hill", [(0, -1.2), (1, -0.8), (2, 1.5), (3, -2.5)])
def test_matches_lmfit(seed, hill):
    lmfit = pytest.importorskip("lmfit")
    x, y = synth(hill=hill, seed=seed)
    ours = fit_dose_response(x, y)
    m = lmfit.Model(lambda x, bottom, top, logic50, hill: model(x, bottom, top, logic50, hill))
    p = m.make_params(bottom=y.min(), top=y.max(), logic50=0.0, hill=1.0 if hill > 0 else -1.0)
    ref = m.fit(y, p, x=x)
    for k in ("bottom", "top", "logic50", "hill"):
        assert ours.params[k].value == pytest.approx(ref.params[k].value, rel=2e-4, abs=2e-4)
        assert ours.params[k].se == pytest.approx(ref.params[k].stderr, rel=5e-3)
    assert ours.sse == pytest.approx(ref.chisqr, rel=1e-6)
    assert ours.df == ref.nfree and ours.r2 == pytest.approx(ref.rsquared, rel=1e-6)


def test_ic50_and_its_ci_come_from_logic50():
    from scipy import stats
    x, y = synth()
    r = fit_dose_response(x, y)
    lg, ic = r.params["logic50"], r.params["ic50"]
    t = stats.t.ppf(0.975, r.df)
    assert ic.value == pytest.approx(10 ** lg.value)
    assert (ic.ci_low, ic.ci_high) == pytest.approx((10 ** (lg.value - t * lg.se), 10 ** (lg.value + t * lg.se)))
    assert ic.ci_low < ic.value < ic.ci_high and r.curve(ic.value) == pytest.approx(
        (r.params["top"].value + r.params["bottom"].value) / 2)


# ---------- ¿el IC95% realmente cubre ~95%? ----------
def test_confidence_interval_coverage_by_simulation():
    hits_log = hits_ic = fails = 0
    N = 150
    for s in range(N):
        x, y = synth(sd=3.0, seed=1000 + s)
        try:
            r = fit_dose_response(x, y)
        except ValueError:
            fails += 1
            continue
        lg = r.params["logic50"]
        hits_log += lg.ci_low <= math.log10(3.0) <= lg.ci_high
        hits_ic += r.params["ic50"].ci_low <= 3.0 <= r.params["ic50"].ci_high
    ok = N - fails
    assert fails == 0
    assert 0.90 <= hits_log / ok <= 0.99 and 0.90 <= hits_ic / ok <= 0.99


# ---------- parámetros fijos ----------
def test_fixed_bottom_top_and_hill():
    x, y = synth(bottom=0.0, top=100.0, hill=-1.0, sd=3.0, seed=5)
    free = fit_dose_response(x, y)
    fx = fit_dose_response(x, y, FitConfig(fix_bottom=0, fix_top=100))
    assert fx.params["bottom"].fixed and fx.params["bottom"].value == 0 and fx.params["top"].value == 100
    assert fx.df == free.df + 2 and math.isnan(fx.params["top"].se)
    assert fx.params["ic50"].value == pytest.approx(3.0, rel=0.15)
    assert fx.params["ic50"].se < free.params["ic50"].se * 1.2        # fijar suele afinar el IC50
    h1 = fit_dose_response(x, y, FitConfig(fix_hill=-1.0))
    assert h1.params["hill"].value == -1.0 and h1.df == free.df + 1


def test_increasing_curve_has_positive_hill():
    x, y = synth(hill=+1.5, seed=7)
    assert fit_dose_response(x, y).params["hill"].value == pytest.approx(1.5, rel=0.25)


def test_noiseless_data_is_recovered_exactly():
    x = DOSES
    y = model(x, 10, 90, math.log10(7.0), -2.0)
    r = fit_dose_response(x, y)
    assert r.params["ic50"].value == pytest.approx(7.0, rel=1e-6) and r.params["hill"].value == pytest.approx(-2.0, rel=1e-6)
    assert r.sse < 1e-12


# ---------- datos problemáticos ----------
def test_zero_and_negative_doses_are_excluded_with_a_note():
    x = np.concatenate([[0.0, 0.0], DOSES])
    y = np.concatenate([[100.0, 99.0], synth()[1]])
    r = fit_dose_response(x, y)
    assert r.excluded == 2 and r.n == len(DOSES) and any("excluyeron" in n for n in r.notes)


def test_too_little_data_raises_clear_errors():
    with pytest.raises(ValueError, match="3 dosis"):
        fit_dose_response([1, 1, 10, 10], [1, 2, 3, 4])
    with pytest.raises(ValueError, match="3 dosis"):
        fit_dose_response([0, 0, 1, 10], [1, 2, 3, 4])               # los ceros no cuentan
    with pytest.raises(ValueError, match="puntos"):
        fit_dose_response([1, 10, 100], [1, 2, 3])                   # 3 puntos, 4 parámetros libres


def test_no_degrees_of_freedom_gives_note_instead_of_fake_ci():
    x = [0.1, 1, 10, 100]
    y = model(np.array(x), 5, 100, 0.5, -1.2)
    r = fit_dose_response(x, y)
    assert r.df == 0 and math.isnan(r.params["ic50"].ci_low) and any("grados de libertad" in n for n in r.notes)


def test_extrapolated_ic50_is_flagged():
    x = np.repeat([1.0, 3, 10, 30, 100], 3)
    y = model(x, 0, 100, math.log10(5000.0), -1.0) + np.random.default_rng(2).normal(0, 0.5, len(x))
    r = fit_dose_response(x, y, FitConfig(fix_bottom=0, fix_top=100))
    assert any("fuera del rango" in n for n in r.notes)


# ---------- varias series y formato ----------
def test_fit_xy_fits_each_series_and_reports_failures():
    xy = XYData("Dosis", list(DOSES), {"A": list(synth(seed=1)[1]), "B": list(synth(ic50=30.0, seed=2)[1]),
                                       "C": [math.nan] * len(DOSES)})
    rep = fit_xy(xy)
    assert set(rep.results) == {"A", "B"} and rep.results["B"].ic50 > 5 * rep.results["A"].ic50
    short = fit_xy(XYData("D", [1.0, 2.0], {"A": [1.0, 2.0]}))
    assert "A" in short.errors and not short.results
    assert fit_xy(XYData()).errors


def test_html_report_contents():
    rep = fit_xy(XYData("Dosis", list(DOSES), {"Línea <A>": list(synth()[1])}))
    h = fit_to_html(rep, FitConfig(fix_bottom=None))
    assert "IC50" in h and "IC95%" in h and "Línea &lt;A&gt;" in h and "Pendiente de Hill" in h
    h2 = fit_to_html(fit_xy(XYData("D", list(DOSES), {"A": list(synth(bottom=0, top=100, seed=3)[1])}), FitConfig(fix_bottom=0, fix_top=100)),
                     FitConfig(fix_bottom=0, fix_top=100, alpha=0.01))
    assert "(fijo)" in h2 and "IC99%" in h2


def test_config_roundtrip():
    c = FitConfig(fix_bottom=0.0, fix_top=100.0, alpha=0.01, active=True)
    assert FitConfig.from_dict(c.to_dict()) == c
    assert FitConfig.from_dict({"alpha": 0.1, "desconocido": 1}).alpha == 0.1


# ---------- regresión: IC enorme desbordaba 10**x (OverflowError) y tumbaba todo el análisis ----------
def test_huge_confidence_interval_does_not_overflow():
    from plotcraft.core.fitting import _pow10
    assert _pow10(400) == math.inf and _pow10(-400) == 0.0 and math.isnan(_pow10(math.nan))
    y = model(DOSES, 5, 100, math.log10(3.0), -1.2) + np.random.default_rng(5013).normal(0, 15, len(DOSES))
    r = fit_dose_response(DOSES, y)                                   # antes: OverflowError
    ic = r.params["ic50"]
    assert math.isinf(ic.ci_high) and any("órdenes de magnitud" in n for n in r.notes)
    h = fit_to_html(fit_xy(XYData("D", list(DOSES), {"A": list(y)})), FitConfig())
    assert "∞" in h
    # una serie mala no debe impedir ver las demás
    ok = list(synth(seed=1)[1])
    rep = fit_xy(XYData("D", list(DOSES), {"mala": list(y), "buena": ok}))
    assert set(rep.results) == {"mala", "buena"}
