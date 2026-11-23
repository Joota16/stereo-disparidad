"""Pruebas T21, sin lanzar benchmarks costosos."""
import numpy as np
import pandas as pd
import pytest

from experiments.analyze_t21 import analyze_runs, identify_crossovers


def sample_records():
    rows = []
    for scene, height, width, times in [
        ("Adirondack_Q (K=7, D=32)", 10, 10,
         {"secuencial": [10, 12], "multiproceso_p2": [6, 7], "distribuido_lan": [15, 17]}),
        ("Adirondack_H (K=7, D=32)", 20, 20,
         {"secuencial": [100, 104], "multiproceso_p2": [60, 62], "distribuido_lan": [80, 84]}),
    ]:
        for mode, values in times.items():
            for t in values:
                rows.append({"caso": scene, "alto": height, "ancho": width,
                             "ventana_K": 7, "d_min": 0, "d_max": 32,
                             "modalidad": mode, "es_calentamiento": False,
                             "equivalente": True, "tiempo_s": t})
            rows.append({"caso": scene, "alto": height, "ancho": width,
                         "ventana_K": 7, "d_min": 0, "d_max": 32,
                         "modalidad": mode, "es_calentamiento": True,
                         "equivalente": True, "tiempo_s": 999})
    return pd.DataFrame(rows)


def test_speedup_y_eficiencia_local():
    summary = analyze_runs(sample_records())
    subset = summary.loc[summary["alto"] == 10]
    seq = subset.loc[subset["modalidad"] == "secuencial"].iloc[0]
    p2 = subset.loc[subset["modalidad"] == "multiproceso_p2"].iloc[0]
    dist = subset.loc[subset["modalidad"] == "distribuido_lan"].iloc[0]
    assert seq["mediana_s"] == 11
    assert p2["mediana_s"] == 6.5
    assert p2["speedup"] == round(11 / 6.5, 5)
    assert p2["eficiencia_local"] == round((11 / 6.5) / 2, 5)
    assert np.isnan(dist["eficiencia_local"])
    assert seq["repeticiones"] == 2


def test_observed_crossover_and_no_interpolation():
    summary = analyze_runs(sample_records())
    crossing, notes = identify_crossovers(summary)
    assert len(crossing) == 1
    assert crossing.iloc[0]["pixeles_desde"] == 100
    assert crossing.iloc[0]["pixeles_hasta"] == 400


def test_equivalence_failure_not_accepted():
    df = sample_records()
    df.loc[0, "equivalente"] = False
    with pytest.raises(ValueError, match="sin equivalencia"):
        analyze_runs(df)


def test_loopback_not_counted_as_distributed():
    df = sample_records()
    loopback = df.iloc[0].copy()
    loopback["modalidad"] = "distribuido_loopback"
    df = pd.concat([df, loopback.to_frame().T], ignore_index=True)
    summary = analyze_runs(df)
    assert "distribuido_loopback" not in set(summary["modalidad"])


def test_no_reference_is_error():
    df = sample_records().loc[lambda d: d["modalidad"] != "secuencial"]
    with pytest.raises(ValueError, match="Falta secuencial"):
        analyze_runs(df)
