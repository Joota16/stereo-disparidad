"""Analisis de rendimiento y calculo de speedup.

Procesa el CSV de corridas individuales y genera resumen estadistico y graficos.
"""

import argparse
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

CONFIG_COLS = ["caso", "alto", "ancho", "ventana_K", "d_min", "d_max"]
REQUIRED_COLS = CONFIG_COLS + [
    "modalidad", "es_calentamiento", "equivalente", "tiempo_s",
]
MODES = ["secuencial", "multiproceso_p2", "multiproceso_p4", "distribuido_lan"]


def parse_bool(col: pd.Series, name: str) -> pd.Series:
    mapping = {"true": True, "false": False, "1": True, "0": False,
               "si": True, "no": False}
    values = col.astype(str).str.strip().str.lower().map(mapping)
    if values.isna().any():
        raise ValueError(f"Columna {name} contiene valores booleanos invalidos")
    return values.astype(bool)


def analyze_runs(runs: pd.DataFrame, include_loopback: bool = False) -> pd.DataFrame:
    """Agrega las repeticiones validadas por configuracion y modalidad.

    El speedup se calcula con medianas del mismo caso, K y rango de disparidad.
    Se exige equivalencia de todas las ejecuciones medidas.
    """
    missing = sorted(set(REQUIRED_COLS) - set(runs.columns))
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")

    df = runs.copy()
    df["es_calentamiento"] = parse_bool(df["es_calentamiento"], "es_calentamiento")
    df["equivalente"] = parse_bool(df["equivalente"], "equivalente")
    df = df.loc[~df["es_calentamiento"]].copy()
    if df.empty:
        raise ValueError("No hay ejecuciones medidas (solo calentamientos)")

    if not df["equivalente"].all():
        bad = df.loc[~df["equivalente"], ["caso", "modalidad"]].head(3)
        raise ValueError(f"Existen ejecuciones sin equivalencia: {bad.to_dict('records')}")

    df["tiempo_s"] = pd.to_numeric(df["tiempo_s"], errors="coerce")
    if (df["tiempo_s"].isna() | ~np.isfinite(df["tiempo_s"]) |
            (df["tiempo_s"] <= 0)).any():
        raise ValueError("Los tiempos deben ser finitos y positivos")
    for col in ["alto", "ancho", "ventana_K", "d_min", "d_max"]:
        df[col] = pd.to_numeric(df[col], errors="raise").astype(int)

    if not include_loopback:
        df = df.loc[df["modalidad"] != "distribuido_loopback"].copy()
    if df.empty:
        raise ValueError("No quedan modalidades tras excluir loopback")

    unknown = sorted(set(df["modalidad"]) - set(MODES) - {"distribuido_loopback"})
    if unknown:
        raise ValueError(f"Modalidades no reconocidas: {unknown}")

    grouped = df.groupby(CONFIG_COLS + ["modalidad"], dropna=False, sort=False)
    result = grouped["tiempo_s"].agg(
        repeticiones="count", media_s="mean", mediana_s="median",
        min_s="min", max_s="max",
    ).reset_index()
    std = grouped["tiempo_s"].apply(lambda x: float(np.std(x.to_numpy(), ddof=0))).reset_index(name="desv_std_s")
    result = result.merge(std, on=CONFIG_COLS + ["modalidad"], how="left", validate="one_to_one")

    baseline = result[result["modalidad"] == "secuencial"][CONFIG_COLS + ["mediana_s"]].rename(
        columns={"mediana_s": "mediana_secuencial_s"}
    )
    result = result.merge(baseline, on=CONFIG_COLS, how="left", validate="many_to_one")
    if result["mediana_secuencial_s"].isna().any():
        raise ValueError("Falta secuencial en al menos una configuracion: speedup no definible")

    result["speedup"] = result["mediana_secuencial_s"] / result["mediana_s"]
    result["eficiencia_local"] = np.nan
    result.loc[result["modalidad"] == "secuencial", "eficiencia_local"] = 1.0
    for mode, n in [("multiproceso_p2", 2), ("multiproceso_p4", 4)]:
        selected = result["modalidad"] == mode
        result.loc[selected, "eficiencia_local"] = result.loc[selected, "speedup"] / n

    result["pixeles"] = result["alto"] * result["ancho"]
    result["speedup"] = result["speedup"].round(5)
    result["eficiencia_local"] = result["eficiencia_local"].round(5)
    result = result.sort_values(["pixeles", "ventana_K", "d_max", "modalidad"])
    return result.reset_index(drop=True)


def identify_crossovers(summary: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Cruces OBSERVADOS entre tamanos, manteniendo K, d_min, d_max y escena.

    No estima un punto exacto entre tamanos medidos ni generaliza a otros equipos.
    """
    def normalize_scene(name: str) -> str:
        prefix = str(name).split(" (")[0]
        return prefix.replace("_Q", "").replace("_H", "").lower()

    dist = summary.loc[summary["modalidad"] == "distribuido_lan"].copy()
    if dist.empty:
        return pd.DataFrame(), ["No hay mediciones LAN entre dos equipos; no puede analizarse cruce distribuido."]
    dist["escena"] = dist["caso"].map(normalize_scene)
    rows = []
    notes = []
    for key, group in dist.groupby(["escena", "ventana_K", "d_min", "d_max"]):
        group = group.sort_values("pixeles")
        unique_sizes = group["pixeles"].nunique()
        if unique_sizes < 2:
            notes.append(f"{key}: solo {unique_sizes} tamano(s), sin cruce evaluable.")
            continue
        # Evita interpretar datos de igual tamano pero distinta escena/ROI como escala distinta.
        previous = None
        for row in group.itertuples(index=False):
            if previous is not None and row.pixeles != previous.pixeles:
                s1 = previous.speedup - 1.0
                s2 = row.speedup - 1.0
                if s1 * s2 < 0:
                    rows.append({"escena": key[0], "ventana_K": key[1],
                                 "d_min": key[2], "d_max": key[3],
                                 "pixeles_desde": previous.pixeles,
                                 "pixeles_hasta": row.pixeles,
                                 "speedup_desde": previous.speedup,
                                 "speedup_hasta": row.speedup,
                                 "interpretacion": "Cambio de signo observado; umbral exacto desconocido"})
            previous = row
        if not any(r["escena"] == key[0] and r["ventana_K"] == key[1] and
                   r["d_min"] == key[2] and r["d_max"] == key[3] for r in rows):
            notes.append(f"{key}: no se observo cruce en tamanos ensayados.")
    return pd.DataFrame(rows), notes


def create_figures(summary: pd.DataFrame, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    unique_cases = summary[CONFIG_COLS + ["pixeles"]].drop_duplicates().sort_values("pixeles")
    case_names = [f"{r.caso}\n{r.alto}x{r.ancho}" for r in unique_cases.itertuples(index=False)]
    x = np.arange(len(case_names))
    lookup = unique_cases.set_index(CONFIG_COLS).index

    for metric, ylabel, name in [
        ("mediana_s", "Mediana del tiempo total (s)", "t21_tiempos.png"),
        ("speedup", "Aceleracion frente a secuencial (x)", "t21_speedup.png"),
    ]:
        fig, ax = plt.subplots(figsize=(max(9, len(case_names) * 1.45), 5.3))
        for mode in MODES:
            table = summary[summary["modalidad"] == mode].set_index(CONFIG_COLS)
            vals = [table.loc[index, metric] if index in table.index else np.nan for index in lookup]
            ax.plot(x, vals, marker="o", label=mode)
        if metric == "speedup":
            ax.axhline(1.0, linestyle="--", linewidth=1, label="Sin aceleracion (1x)")
        ax.set_xticks(x, case_names, rotation=30, ha="right")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(output / name, dpi=160)
        plt.close(fig)


def write_conclusions(summary: pd.DataFrame, crossovers: pd.DataFrame,
                      notes: List[str], output: Path, included_loopback: bool) -> None:
    lines = [
        "# Analisis de rendimiento SAD",
        "",
        "Las cifras proceden de las corridas medidas; se excluyen los calentamientos.",
        "El speedup se obtiene de la mediana secuencial y la mediana de cada modalidad",
        "para la misma configuración. La eficiencia es speedup/procesos SOLO para CPU",
        "local homogénea (p2 y p4). No se atribuye eficiencia homogénea a dos nodos.",
        "",
        f"Loopback incluido: **{'sí, solo como control' if included_loopback else 'no'}**.",
        "Los resultados de loopback no demuestran distribución entre dos equipos.",
        "",
        "## Comparaciones por configuración",
        "",
        "| Caso | Arquitectura | n | Mediana (s) | Speedup | Eficiencia local |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in summary.itertuples(index=False):
        eff = f"{r.eficiencia_local:.3f}" if np.isfinite(r.eficiencia_local) else "N/A"
        lines.append(f"| {r.caso} | {r.modalidad} | {r.repeticiones} | {r.mediana_s:.4f} | {r.speedup:.3f} | {eff} |")
    lines.extend(["", "## Punto de cruce observado", ""])
    if not crossovers.empty:
        for r in crossovers.itertuples(index=False):
            lines.append(f"- {r.escena}, K={r.ventana_K}, D=[{r.d_min},{r.d_max}): "
                         f"el speedup pasó de {r.speedup_desde:.3f}x a "
                         f"{r.speedup_hasta:.3f}x entre {r.pixeles_desde} y {r.pixeles_hasta} píxeles.")
    else:
        lines.append("No se identificó un cruce medido en las configuraciones comparables disponibles.")
    lines.extend(["", "### Limitaciones", ""])
    lines.extend(f"- {line}" for line in notes)
    lines.extend([
        "- Un cruce observado entre dos tamaños **no establece** el umbral exacto.",
        "- La ausencia de cruce no prueba que nunca exista para cargas mayores.",
        "- Esta descripción no constituye un test de significación estadística.",
        "- Comparar únicamente experimentos con la misma configuración y entorno documentado.",
    ])
    (output / "t21_interpretacion.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analisis de speedup y eficiencia local")
    parser.add_argument("--runs", required=True, help="CSV de repeticiones medido")
    parser.add_argument("--output", default="results/t21", help="Carpeta de salidas")
    parser.add_argument("--include-loopback", action="store_true", help="Incluir control loopback, nunca como LAN real")
    args = parser.parse_args()

    path = Path(args.runs)
    if not path.is_file():
        parser.error(f"No existe el CSV: {path}")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(path)
    summary = analyze_runs(data, include_loopback=args.include_loopback)
    cross, notes = identify_crossovers(summary)
    summary.to_csv(output / "t21_resumen.csv", index=False, encoding="utf-8")
    if not cross.empty:
        cross.to_csv(output / "t21_cruces_observados.csv", index=False, encoding="utf-8")
    write_conclusions(summary, cross, notes, output, args.include_loopback)
    create_figures(summary, output)
    print(f"{len(summary)} resultados por configuracion y arquitectura")
    print(f"Cruces observados: {len(cross)} (no se interpola umbral exacto)")
    print(f"Archivos generados: {output.resolve()}")


if __name__ == "__main__":
    main()
