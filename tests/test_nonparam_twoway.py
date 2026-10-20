import itertools
import math

import numpy as np
import pytest
from scipy import stats

from plotcraft.core.analysis import AnalysisConfig, analyze, analyze_twoway, posthoc_choices
from plotcraft.core.posthoc import adjust_p, run_posthoc_stats
from plotcraft.core.twoway import COMPARE_MODES, TwoWayData, anova_two_way

A = [10.0, 12, 11, 13, 9, 14]
B = [14.0, 15, 13, 16, 15, 17]
GC = [20.0, 19, 22, 21, 18, 23]
D = [12.0, 12, 15, 11, 14, 15]     # con empates
DATA = {"A": A, "B": B, "C": GC, "D": D}


# ---------- no paramétricas ----------
def test_mann_whitney_matches_scipy():
    r = analyze({"A": A, "D": D}, AnalysisConfig(test="Mann-Whitney"))
    ref = stats.mannwhitneyu(A, D, alternative="two-sided")
    c = r.comparisons[0]
    assert c.stat == pytest.approx(ref.statistic) and c.p == pytest.approx(ref.pvalue)
    assert c.diff == pytest.approx(np.median(A) - np.median(D))


def test_wilcoxon_matches_scipy():
    r = analyze({"A": A, "B": B}, AnalysisConfig(test="Wilcoxon (apareada)"))
    ref = stats.wilcoxon(A, B)
    assert r.comparisons[0].stat == pytest.approx(ref.statistic) and r.comparisons[0].p == pytest.approx(ref.pvalue)
    with pytest.raises(ValueError):
        analyze({"A": A, "B": B[:4]}, AnalysisConfig(test="Wilcoxon (apareada)"))


def test_kruskal_matches_scipy():
    r = analyze(DATA, AnalysisConfig(test="Kruskal-Wallis", posthoc="Ninguno"))
    ref = stats.kruskal(*DATA.values())
    assert r.summary[0][1] == f"{ref.statistic:.4g}" and r.comparisons == []


@pytest.mark.parametrize("method,sp", [("Bonferroni", "bonferroni"), ("Holm", "holm"), ("Sidak", "sidak")])
def test_dunn_matches_scikit_posthocs(method, sp):
    skp = pytest.importorskip("scikit_posthocs")
    r = analyze(DATA, AnalysisConfig(test="Kruskal-Wallis", posthoc=f"Dunn-{method}"))
    ref = skp.posthoc_dunn([np.array(v) for v in DATA.values()], p_adjust=sp)
    for c in r.comparisons:
        i, j = list(DATA).index(c.a) + 1, list(DATA).index(c.b) + 1
        assert c.p == pytest.approx(ref.loc[i, j], abs=1e-9)


def test_friedman_matches_scipy_and_dunn_formula():
    d = {k: v for k, v in DATA.items() if k != "D"}
    r = analyze(d, AnalysisConfig(test="Friedman", posthoc="Dunn-Bonferroni"))
    ref = stats.friedmanchisquare(*d.values())
    assert r.summary[0][1] == f"{ref.statistic:.4g}"
    M = np.column_stack(list(d.values()))
    R = np.apply_along_axis(stats.rankdata, 1, M).sum(0)
    se = math.sqrt(6 * 3 * 4 / 6)
    z = (R[0] - R[1]) / se
    assert r.comparisons[0].stat == pytest.approx(z)
    assert r.comparisons[0].p == pytest.approx(min(1, 3 * 2 * stats.norm.sf(abs(z))))
    with pytest.raises(ValueError):
        analyze({"A": A, "B": B}, AnalysisConfig(test="Friedman"))


def test_adjust_p_matches_statsmodels():
    mt = pytest.importorskip("statsmodels.stats.multitest")
    raw = [0.001, 0.02, 0.04, 0.3, 0.5]
    for m, sm in [("Bonferroni", "bonferroni"), ("Sidak", "sidak"), ("Holm", "holm"), ("Holm-Sidak", "holm-sidak")]:
        assert adjust_p(raw, m) == pytest.approx(mt.multipletests(raw, method=sm)[1])


def test_posthoc_choices_per_test():
    assert "Dunnett" in posthoc_choices("ANOVA de una vía")
    assert posthoc_choices("Kruskal-Wallis")[0] == "Dunn-Bonferroni"
    assert posthoc_choices("Mann-Whitney") == ()
    assert "Dunnett" not in posthoc_choices("ANOVA de dos vías")


# ---------- ANOVA de dos vías ----------
def make_td(cells, a_name="Trat", b_name="Tiempo"):
    a, b, y = [], [], []
    for (la, lb), vals in cells.items():
        for v in vals:
            a.append(la); b.append(lb); y.append(float(v))
    return TwoWayData(a_name, b_name, "Viab", a, b, y)


BALANCED = {("C", "24h"): [10, 12, 11], ("C", "48h"): [8, 9, 7], ("T", "24h"): [15, 14, 16],
            ("T", "48h"): [25, 27, 26], ("U", "24h"): [12, 13, 11], ("U", "48h"): [12, 11, 13]}
UNBALANCED = {("C", "24h"): [10, 12, 11, 13], ("C", "48h"): [8, 9], ("T", "24h"): [15, 14, 16],
              ("T", "48h"): [25, 27, 26, 24, 28], ("U", "24h"): [12], ("U", "48h"): [12, 11, 13]}


@pytest.mark.parametrize("cells", [BALANCED, UNBALANCED])
def test_two_way_matches_statsmodels_type3(cells):
    smf = pytest.importorskip("statsmodels.formula.api")
    sma = pytest.importorskip("statsmodels.stats.anova")
    pd = pytest.importorskip("pandas")
    td = make_td(cells)
    df = pd.DataFrame({"A": td.a, "B": td.b, "y": td.y})
    model = smf.ols("y ~ C(A, Sum) * C(B, Sum)", df).fit()
    tab = sma.anova_lm(model, typ=3)
    rows, mse, dfe, rss = anova_two_way(td)
    keys = {"A": "C(A, Sum)", "B": "C(B, Sum)", "AB": "C(A, Sum):C(B, Sum)"}
    for key, ss, d, ms, F, p in rows:
        ref = tab.loc[keys[key]]
        assert ss == pytest.approx(ref["sum_sq"]) and d == ref["df"]
        assert F == pytest.approx(ref["F"]) and p == pytest.approx(ref["PR(>F)"])
    assert rss == pytest.approx(tab.loc["Residual", "sum_sq"]) and dfe == tab.loc["Residual", "df"]


def test_two_way_balanced_ss_adds_up_and_pct():
    r = analyze_twoway(make_td(BALANCED), AnalysisConfig(test="ANOVA de dos vías"))
    ss = [row[1] for row in r.anova]
    assert sum(ss[:4]) == pytest.approx(ss[4])
    assert sum(row[6] for row in r.anova[:4]) == pytest.approx(100.0)
    assert len(r.groups) == 6


def test_two_way_simple_effects_are_corrected_within_family():
    td = make_td(BALANCED)
    cfg = AnalysisConfig(test="ANOVA de dos vías", posthoc="Bonferroni", twoway_compare=COMPARE_MODES[0])
    r = analyze_twoway(td, cfg)
    # leyenda dentro de cada X: 3 grupos X, 1 comparación (24h vs 48h) por familia
    assert len(r.comparisons) == 3
    c = r.comparisons[0]
    assert c.a_key == ("C", "24h") and c.b_key == ("C", "48h")
    _, mse, dfe, _ = anova_two_way(td)
    se = math.sqrt(mse * (1 / 3 + 1 / 3))
    t = (np.mean([10, 12, 11]) - np.mean([8, 9, 7])) / se
    assert c.p == pytest.approx(2 * stats.t.sf(abs(t), dfe))      # familia de 1 -> sin ajuste extra
    r2 = analyze_twoway(td, AnalysisConfig(test="ANOVA de dos vías", posthoc="Bonferroni", twoway_compare=COMPARE_MODES[1]))
    assert len(r2.comparisons) == 2 * 3                           # 2 niveles de leyenda x 3 pares de X


def test_two_way_tukey_equals_t_for_two_means():
    td = make_td(BALANCED)
    t1 = analyze_twoway(td, AnalysisConfig(posthoc="Tukey", twoway_compare=COMPARE_MODES[0]))
    t2 = analyze_twoway(td, AnalysisConfig(posthoc="Bonferroni", twoway_compare=COMPARE_MODES[0]))
    assert [c.p for c in t1.comparisons] == pytest.approx([c.p for c in t2.comparisons], rel=1e-6)


def test_two_way_tukey_with_external_mse_matches_statsmodels_one_way():
    sm = pytest.importorskip("statsmodels.stats.multicomp")
    ns = np.array([5.0, 5, 5]); samples = [np.array(v) for v in (A[:5], B[:5], GC[:5])]
    means = np.array([s.mean() for s in samples])
    mse = sum(((s - s.mean()) ** 2).sum() for s in samples) / 12
    got = run_posthoc_stats("Tukey", ["A", "B", "C"], ns, means, mse, 12, 0.05)
    tk = sm.pairwise_tukeyhsd(np.concatenate(samples), np.repeat(list("ABC"), 5))
    assert [c.p for c in got] == pytest.approx(list(tk.pvalues), abs=1e-6)


def test_two_way_errors():
    cfg = AnalysisConfig()
    with pytest.raises(ValueError):
        analyze_twoway(TwoWayData(), cfg)
    with pytest.raises(ValueError):                                  # una celda vacía
        analyze_twoway(make_td({k: v for k, v in BALANCED.items() if k != ("U", "48h")}), cfg)
    with pytest.raises(ValueError):                                  # sin réplicas
        analyze_twoway(make_td({k: [v[0]] for k, v in BALANCED.items()}), cfg)
    with pytest.raises(ValueError):                                  # un solo nivel
        analyze_twoway(make_td({("C", "24h"): [1, 2], ("C", "48h"): [3, 4]}), cfg)


def test_swapped_and_roundtrip():
    td = make_td(BALANCED)
    sw = td.swapped()
    assert sw.a_name == "Tiempo" and sw.a == td.b
    assert TwoWayData.from_dict(td.to_dict()) == td
