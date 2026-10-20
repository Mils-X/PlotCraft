import math

import numpy as np
import pytest
from scipy import stats

from plotcraft.core.analysis import AnalysisConfig, analyze, stars
from plotcraft.core.plotting import make_bar_figure
from plotcraft.core.posthoc import POSTHOC_METHODS, run_posthoc
from plotcraft.core.style import PlotStyle

A = [10.0, 12, 11, 13, 9]
B = [14.0, 15, 13, 16, 15]
C = [20.0, 19, 22, 21, 18]
D = [12.0, 18, 15, 11, 14, 17]          # n distinto (desbalanceado)
DATA3 = {"A": A, "B": B, "C": C}


# ---------- t ----------
@pytest.mark.parametrize("test,eq", [("t de Student", True), ("t de Welch", False)])
def test_t_matches_scipy(test, eq):
    r = analyze({"A": A, "D": D}, AnalysisConfig(test=test))
    ref = stats.ttest_ind(A, D, equal_var=eq)
    c = r.comparisons[0]
    assert c.stat == pytest.approx(ref.statistic) and c.p == pytest.approx(ref.pvalue)
    assert c.ci_low < c.diff < c.ci_high
    ci = ref.confidence_interval(0.95)
    assert (c.ci_low, c.ci_high) == pytest.approx((ci.low, ci.high))


def test_paired_matches_scipy():
    r = analyze({"A": A, "B": B}, AnalysisConfig(test="t apareada"))
    ref = stats.ttest_rel(A, B)
    assert r.comparisons[0].stat == pytest.approx(ref.statistic)
    assert r.comparisons[0].p == pytest.approx(ref.pvalue)
    with pytest.raises(ValueError):
        analyze({"A": A, "D": D}, AnalysisConfig(test="t apareada"))


def test_t_errors():
    with pytest.raises(ValueError):
        analyze(DATA3, AnalysisConfig(test="t de Student"))
    with pytest.raises(ValueError):
        analyze({"A": [1.0], "B": [2.0, 3.0]}, AnalysisConfig(test="t de Student"))
    with pytest.raises(ValueError):
        analyze({"A": A}, AnalysisConfig())


def test_auto_choice():
    assert analyze({"A": A, "B": B}, AnalysisConfig()).title.startswith("t de Welch")
    assert analyze(DATA3, AnalysisConfig()).title == "ANOVA de una vía"


# ---------- ANOVA ----------
def test_anova_matches_scipy():
    d = {"A": A, "B": B, "C": C, "D": D}
    r = analyze(d, AnalysisConfig(posthoc="Ninguno"))
    ref = stats.f_oneway(*d.values())
    _, ssb, dfb, msb, F, p, _pct = r.anova[0]
    assert F == pytest.approx(ref.statistic) and p == pytest.approx(ref.pvalue)
    assert r.anova[0][1] + r.anova[1][1] == pytest.approx(r.anova[2][1])
    assert r.comparisons == []


# ---------- post hoc vs statsmodels ----------
def _long(d):
    y = np.concatenate([np.array(v, float) for v in d.values()])
    g = np.concatenate([[k] * len(v) for k, v in d.items()])
    return y, g


@pytest.mark.parametrize("d", [DATA3, {"A": A, "B": B, "C": C, "D": D}])
def test_tukey_matches_statsmodels(d):
    sm = pytest.importorskip("statsmodels.stats.multicomp")
    y, g = _long(d)
    tk = sm.pairwise_tukeyhsd(y, g, alpha=0.05)
    r = analyze(d, AnalysisConfig(posthoc="Tukey"))
    assert [c.p for c in r.comparisons] == pytest.approx(list(tk.pvalues), abs=1e-6)
    # statsmodels reporta (grupo2 - grupo1); aquí es (a - b): mismo intervalo con signo invertido
    lo, hi = tk.confint[:, 0], tk.confint[:, 1]
    assert [c.ci_low for c in r.comparisons] == pytest.approx(list(-hi), abs=1e-6)
    assert [c.ci_high for c in r.comparisons] == pytest.approx(list(-lo), abs=1e-6)
    assert [c.diff for c in r.comparisons] == pytest.approx(list(-tk.meandiffs), abs=1e-9)


@pytest.mark.parametrize("method,sm_name", [("Bonferroni", "bonferroni"), ("Sidak", "sidak"),
                                            ("Holm-Sidak", "holm-sidak")])
def test_pooled_adjustments_match_statsmodels(method, sm_name):
    mt = pytest.importorskip("statsmodels.stats.multitest")
    d = {"A": A, "B": B, "C": C, "D": D}
    names, samples = list(d), [np.array(v, float) for v in d.values()]
    N, k = sum(map(len, samples)), len(samples)
    mse = sum(((s - s.mean()) ** 2).sum() for s in samples) / (N - k)
    raw = []
    for i in range(k):
        for j in range(i + 1, k):
            se = math.sqrt(mse * (1 / len(samples[i]) + 1 / len(samples[j])))
            t = (samples[i].mean() - samples[j].mean()) / se
            raw.append(2 * stats.t.sf(abs(t), N - k))
    expected = mt.multipletests(raw, method=sm_name)[1]
    got = [c.p for c in run_posthoc(method, names, samples)]
    assert got == pytest.approx(list(expected), abs=1e-9)


def test_dunnett_matches_scipy_and_is_between_raw_and_bonferroni():
    r = analyze(DATA3, AnalysisConfig(posthoc="Dunnett", control="A"))
    ref = stats.dunnett(B, C, control=A)
    assert [c.p for c in r.comparisons] == pytest.approx(list(ref.pvalue), abs=2e-3)  # scipy es estocástico
    again = analyze(DATA3, AnalysisConfig(posthoc="Dunnett", control="A"))
    assert [c.p for c in again.comparisons] == [c.p for c in r.comparisons]          # reproducible
    assert [(c.a, c.b) for c in r.comparisons] == [("B", "A"), ("C", "A")]
    assert r.comparisons[0].diff == pytest.approx(np.mean(B) - np.mean(A))
    # Dunnett (2 comparaciones vs control) debe quedar entre la p sin ajustar y la de Bonferroni con m=2.
    # Tolerancia 2e-3: precisión de la integración numérica de scipy.
    bonf3 = {(c.a, c.b): c.p for c in run_posthoc("Bonferroni", list(DATA3), [np.array(v, float) for v in DATA3.values()])}
    for c in r.comparisons:
        raw = bonf3[(c.b, c.a)] / 3
        assert raw - 2e-3 <= c.p <= 2 * raw + 2e-3
    with pytest.raises(ValueError):
        run_posthoc("Dunnett", list(DATA3), [np.array(v, float) for v in DATA3.values()], 0.05, "X")


def test_snk_properties():
    names, samples = list(DATA3), [np.array(v, float) for v in DATA3.values()]
    # con 2 grupos SNK == t de Student con MSE combinado == Tukey
    two = run_posthoc("Newman-Keuls", names[:2], samples[:2])[0]
    tk = run_posthoc("Tukey", names[:2], samples[:2])[0]
    assert two.p == pytest.approx(tk.p, rel=1e-6)
    # SNK nunca es más conservador que Tukey en el rango máximo (mismo q, mismo r)
    snk = {(c.a, c.b): c.p for c in run_posthoc("Newman-Keuls", names, samples)}
    tuk = {(c.a, c.b): c.p for c in run_posthoc("Tukey", names, samples)}
    assert snk[("A", "C")] == pytest.approx(tuk[("A", "C")], rel=1e-6)   # rango completo
    assert all(snk[k] <= tuk[k] + 1e-9 for k in snk)
    assert all(0 <= p <= 1 for p in snk.values())


def test_snk_stepdown_monotonic():
    # grupos casi idénticos salvo uno: los pares dentro de un rango n.s. no pueden ser significativos
    d = {"A": [10.0, 10.2, 9.8, 10.1], "B": [10.3, 10.1, 9.9, 10.2],
         "C": [10.4, 10.0, 10.2, 10.3], "D": [20.0, 20.2, 19.8, 20.1]}
    names, samples = list(d), [np.array(v) for v in d.values()]
    snk = {(c.a, c.b): c.p for c in run_posthoc("Newman-Keuls", names, samples)}
    assert snk[("A", "D")] < 0.001 and snk[("A", "B")] > 0.05 and snk[("A", "C")] > 0.05


@pytest.mark.parametrize("method", POSTHOC_METHODS)
def test_all_methods_run_and_are_valid(method):
    r = analyze({"A": A, "B": B, "C": C, "D": D}, AnalysisConfig(posthoc=method, control="B"))
    assert r.comparisons and all(0 <= c.p <= 1 for c in r.comparisons)


def test_stars():
    assert [stars(p) for p in (0.5, 0.04, 0.005, 0.0005, 0.00001)] == ["ns", "*", "**", "***", "****"]
    assert stars(0.04, alpha=0.01) == "ns"


def test_brackets_drawn():
    fig = make_bar_figure(DATA3, PlotStyle(), comparisons=[("A", "B", "**"), ("A", "C", "****"), ("B", "C", "ns")])
    ax = fig.axes[0]
    texts = [t.get_text() for t in ax.texts]
    assert sorted(texts) == ["**", "****", "ns"]
    top_bar = max(np.mean(v) for v in DATA3.values())
    assert ax.get_ylim()[1] > top_bar


def test_html_shows_tiny_p_values():
    from plotcraft.core.analysis import result_to_html
    d = {"A": [1.0, 1.1, 0.9, 1.0], "B": [10.0, 10.1, 9.9, 10.0], "C": [20.0, 20.1, 19.9, 20.0]}
    h = result_to_html(analyze(d, AnalysisConfig()))
    assert "&lt;0.0001" in h and "<0.0001" not in h.replace("&lt;0.0001", "")
