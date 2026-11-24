"""Consolidacion de resultados experimentales en resolucion Quarter."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CASES = {
    (7, 32): "results/t21_ultimo_10rep.txt",
    (7, 64): "results/t21_ultimo_D64_10rep.txt",
    (15, 32): "results/t21_ultimo_K15_D32_10rep.txt",
    (15, 64): "results/t21_ultimo_K15_D64_10rep.txt",
}
QUALITY = {
    (7, 32): "results/t20_Adirondack_Q_K7_D32_20261122_233451/t20_metricas_calidad.csv",
    (7, 64): "results/t20_Adirondack_Q_K7_D64_20261122_233535/t20_metricas_calidad.csv",
    (15, 32): "results/t20_Adirondack_Q_K15_D32_20261123_002356/t20_metricas_calidad.csv",
    (15, 64): "results/t20_Adirondack_Q_K15_D64_20261123_002444/t20_metricas_calidad.csv",
}
STRATA_K7 = Path("results/t20_analisis_por_rango/metricas_estratificadas.csv")
MODES = ("secuencial", "multiproceso_p2", "multiproceso_p4", "distribuido_lan")
MODE_LABELS = {"secuencial": "Secuencial", "multiproceso_p2": "P2",
               "multiproceso_p4": "P4", "distribuido_lan": "LAN"}
CONFIG = ["caso", "alto", "ancho", "ventana_K", "d_min", "d_max"]
GROUP = CONFIG + ["modalidad"]


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def boolean(series: pd.Series, name: str) -> pd.Series:
    values = series.astype(str).str.strip().str.lower().map({
        "true": True, "false": False, "1": True, "0": False,
    })
    if values.isna().any():
        raise ValueError(f"Booleanos invalidos en {name}")
    return values.astype(bool)


def source_runs(pointer: str) -> Path:
    p = Path(pointer)
    if not p.is_file():
        raise FileNotFoundError(f"Falta el puntero del experimento: {p}")
    folder = Path(p.read_text(encoding="utf-8-sig").strip())
    path = folder / "runs.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Falta CSV del experimento: {path}")
    return path


def load_runs() -> tuple[pd.DataFrame, list[Path]]:
    frames, sources = [], []
    required = set(GROUP + ["tiempo_s", "es_calentamiento", "equivalente", "tipo_conexion"])
    for (k, d), pointer in CASES.items():
        path = source_runs(pointer)
        frame = pd.read_csv(path)
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{path}: faltan columnas {sorted(missing)}")
        for col in ["alto", "ancho", "ventana_K", "d_min", "d_max"]:
            frame[col] = pd.to_numeric(frame[col], errors="raise").astype(int)
        if not ((frame["ventana_K"] == k) & (frame["d_max"] == d) &
                (frame["d_min"] == 0)).all():
            raise ValueError(f"{path}: los parametros no corresponden a K{k}-D{d}")
        if set(frame["modalidad"]) != set(MODES):
            raise ValueError(f"{path}: modalidades inesperadas")
        dist = frame.loc[frame["modalidad"] == "distribuido_lan", "tipo_conexion"]
        if not (dist == "lan_remota").all():
            raise ValueError(f"{path}: el distribuido no consta como LAN remota")
        frame["es_calentamiento"] = boolean(frame["es_calentamiento"], "es_calentamiento")
        frame["equivalente"] = boolean(frame["equivalente"], "equivalente")
        frame["tiempo_s"] = pd.to_numeric(frame["tiempo_s"], errors="raise")
        if not frame["equivalente"].all():
            raise ValueError(f"{path}: hay ejecuciones sin equivalencia exacta")
        if not (np.isfinite(frame["tiempo_s"]) & (frame["tiempo_s"] > 0)).all():
            raise ValueError(f"{path}: tiempos invalidos")
        frame["fuente"] = str(path)
        frame["experimento"] = f"K{k}_D{d}"
        measured = frame.loc[~frame["es_calentamiento"]]
        warm = frame.loc[frame["es_calentamiento"]]
        for subset, expected, label in ((measured, 10, "mediciones"), (warm, 1, "calentamientos")):
            counts = subset.groupby(GROUP).size()
            if len(counts) != 12 or not (counts == expected).all():
                raise ValueError(f"{path}: {label} incompletos; se esperan 12 grupos x {expected}")
        if measured[CONFIG].drop_duplicates().shape[0] != 3:
            raise ValueError(f"{path}: se esperaban tres regiones de interes")
        sizes = set(map(tuple, measured[["alto", "ancho"]].drop_duplicates().to_numpy()))
        if sizes != {(96, 160), (160, 256), (224, 352)}:
            raise ValueError(f"{path}: tamaños de ROI inesperados: {sizes}")
        frames.append(frame)
        sources.append(path)
    full = pd.concat(frames, ignore_index=True)
    if len(full) != 528 or int((~full["es_calentamiento"]).sum()) != 480:
        raise AssertionError("Total esperado: 480 medidas y 48 calentamientos")
    return full, sources


def summarize(full: pd.DataFrame) -> pd.DataFrame:
    measured = full.loc[~full["es_calentamiento"]].copy()
    summary = measured.groupby(GROUP, sort=True)["tiempo_s"].agg(
        repeticiones="count", media_s="mean", mediana_s="median",
        desv_std_s=lambda s: np.std(s.to_numpy(), ddof=0),
        minimo_s="min", maximo_s="max",
    ).reset_index()
    if len(summary) != 48 or not (summary["repeticiones"] == 10).all():
        raise AssertionError("Se esperan 48 agregados con diez repeticiones")
    seq = summary.loc[summary["modalidad"] == "secuencial", CONFIG + ["mediana_s"]].rename(
        columns={"mediana_s": "mediana_base_s"}
    )
    summary = summary.merge(seq, on=CONFIG, validate="many_to_one")
    summary["speedup"] = summary["mediana_base_s"] / summary["mediana_s"]
    summary["eficiencia_local"] = np.nan
    summary.loc[summary["modalidad"] == "secuencial", "eficiencia_local"] = 1.0
    for m, p in (("multiproceso_p2", 2), ("multiproceso_p4", 4)):
        sel = summary["modalidad"] == m
        summary.loc[sel, "eficiencia_local"] = summary.loc[sel, "speedup"] / p
    summary["pixeles"] = summary["alto"] * summary["ancho"]
    return summary.sort_values(["ventana_K", "d_max", "pixeles", "modalidad"]).reset_index(drop=True)


def load_quality() -> tuple[pd.DataFrame, pd.DataFrame, list[Path]]:
    parts, source_paths = [], []
    columns = ["modalidad", "ventana_K", "d_max", "mae_epe_px", "rmse_px",
               "bad_pixel_ratio_pct", "invalid_ratio_pct", "cobertura_rango_gt_pct"]
    for (k, d), name in QUALITY.items():
        p = Path(name)
        if not p.is_file():
            raise FileNotFoundError(f"Falta archivo de calidad: {p}")
        data = pd.read_csv(p)
        missing = set(columns) - set(data.columns)
        if missing:
            raise ValueError(f"{p}: faltan columnas de calidad {missing}")
        if len(data) != 2 or set(data["modalidad"]) != {"secuencial", "multiproceso_p4"}:
            raise ValueError(f"{p}: se requieren dos modos: secuencial y P4")
        if not ((pd.to_numeric(data["ventana_K"]) == k) &
                (pd.to_numeric(data["d_max"]) == d)).all():
            raise ValueError(f"{p}: K/D no coinciden")
        for metric in columns[3:]:
            data[metric] = pd.to_numeric(data[metric], errors="raise")
        if not np.isfinite(data[columns[3:]].to_numpy(dtype=float)).all():
            raise ValueError(f"{p}: hay metricas no finitas")
        for metric in columns[3:]:
            vals = data[metric].to_numpy(dtype=float)
            if not np.isclose(vals[0], vals[1], rtol=0, atol=1e-8):
                raise ValueError(f"{p}: la calidad secuencial y P4 difiere")
        data["fuente"] = str(p)
        parts.append(data)
        source_paths.append(p)
    q = pd.concat(parts, ignore_index=True)
    strata = pd.DataFrame()
    if STRATA_K7.is_file():
        strata = pd.read_csv(STRATA_K7)
        if (len(strata) != 4 or set(pd.to_numeric(strata["d_max"])) != {32, 64} or
                set(strata["grupo_gt"]) != {"GT_0_32", "GT_32_64"}):
            raise ValueError(f"{STRATA_K7}: estratos K7 incompletos")
        source_paths.append(STRATA_K7)
    return q, strata, source_paths


def data_by_config(summary: pd.DataFrame, k: int, d: int, metric: str):
    sub = summary[(summary["ventana_K"] == k) & (summary["d_max"] == d)]
    values = {}
    sizes = [(96, 160), (160, 256), (224, 352)]
    for mode in MODES:
        v = []
        for h, w in sizes:
            s = sub[(sub["alto"] == h) & (sub["ancho"] == w) & (sub["modalidad"] == mode)]
            if len(s) != 1:
                raise ValueError(f"Falta K{k}-D{d} {h}x{w} {mode}")
            v.append(float(s.iloc[0][metric]))
        values[mode] = v
    return values


def save_fig(fig, path: Path):
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def charts(summary: pd.DataFrame, full: pd.DataFrame, quality: pd.DataFrame,
           strata: pd.DataFrame, folder: Path):
    names = ["96×160", "160×256", "224×352"]
    x = np.arange(3)
    # Cuatro figuras de tiempos, separadas para evitar confundir parámetros.
    for k, d in CASES:
        vals = data_by_config(summary, k, d, "mediana_s")
        fig, ax = plt.subplots(figsize=(10, 5.8))
        for i, mode in enumerate(MODES):
            bars = ax.bar(x + (i - 1.5) * .2, vals[mode], .2, label=MODE_LABELS[mode])
            ax.bar_label(bars, fmt="%.2f", fontsize=8, padding=2)
        ax.set_xticks(x, names)
        ax.set_xlabel("Región (píxeles)")
        ax.set_ylabel("Mediana de tiempo (s)")
        ax.set_title(f"Tiempo SAD | K{k}, D=[0,{d}) | n=10")
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
        ax.legend(ncol=4, fontsize=9)
        ax.set_ylim(0, max(max(v) for v in vals.values()) * 1.2)
        save_fig(fig, folder / f"t22_tiempos_K{k}_D{d}.png")

    # Dos figuras de speedup con comparación D32/D64 en cada ventana K.
    for k in (7, 15):
        fig, ax = plt.subplots(figsize=(10, 5.8))
        for d in (32, 64):
            vals = data_by_config(summary, k, d, "speedup")
            for mode in ("multiproceso_p2", "multiproceso_p4", "distribuido_lan"):
                ax.plot(x, vals[mode], marker="o", label=f"{MODE_LABELS[mode]} D{d}")
        ax.axhline(1.0, linestyle="--", color="gray", label="Secuencial (1×)")
        ax.set_xticks(x, names)
        ax.set_xlabel("Región (píxeles)")
        ax.set_ylabel("Speedup (mediana Ts / mediana Tp)")
        ax.set_title(f"Aceleración SAD | K{k}, D32 y D64")
        ax.grid(axis="y", alpha=.22)
        ax.legend(ncol=2, fontsize=9)
        save_fig(fig, folder / f"t22_speedup_K{k}.png")

    # Dos figuras de costo remoto vs local: duración de etapas solapadas, no sumarlas.
    lan = full[(full["modalidad"] == "distribuido_lan") & ~full["es_calentamiento"]].copy()
    for column in ("local_compute_s", "remote_compute_s", "receive_wait_s"):
        if column not in lan.columns:
            raise ValueError(f"Falta columna de etapa: {column}")
        lan[column] = pd.to_numeric(lan[column], errors="raise")
    for k in (7, 15):
        sub = lan[lan["ventana_K"] == k]
        agg = sub.groupby(["d_max", "alto", "ancho"])[
            ["local_compute_s", "remote_compute_s", "receive_wait_s"]].median().reset_index()
        agg = agg.sort_values(["d_max", "alto", "ancho"])
        if len(agg) != 6:
            raise ValueError(f"Etapas LAN K{k}: se esperaban seis configuraciones")
        labels = [f"{int(r.alto)}×{int(r.ancho)}\nD{int(r.d_max)}" for r in agg.itertuples()]
        xpos = np.arange(len(agg))
        fig, ax = plt.subplots(figsize=(11, 5.8))
        ax.bar(xpos - .19, agg["local_compute_s"], .38, label="Cálculo local")
        ax.bar(xpos + .19, agg["remote_compute_s"], .38, label="Cálculo remoto")
        ax.set_xticks(xpos, labels)
        ax.set_ylabel("Mediana de etapa (s)")
        ax.set_title(f"Etapas de cómputo LAN | K{k} | duraciones solapadas")
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
        ax.legend()
        save_fig(fig, folder / f"t22_computo_local_remoto_K{k}.png")
        agg.to_csv(folder.parent / f"t22_etapas_LAN_K{k}.csv", index=False, encoding="utf-8-sig")

    seq = quality[quality["modalidad"] == "secuencial"].copy()
    seq = seq.sort_values(["ventana_K", "d_max"])
    labels = [f"K{int(r.ventana_K)}\nD{int(r.d_max)}" for r in seq.itertuples()]
    xc = np.arange(4)
    for col, unit, fname, title in [
        ("mae_epe_px", "MAE (píxeles)", "t22_calidad_MAE.png", "Error absoluto medio"),
        ("rmse_px", "RMSE (píxeles)", "t22_calidad_RMSE.png", "Raíz del error cuadrático medio"),
        ("bad_pixel_ratio_pct", "Píxeles incorrectos (%)", "t22_calidad_bad_pixels.png", "Error mayor que 1 píxel"),
        ("invalid_ratio_pct", "Píxeles inválidos (%)", "t22_calidad_invalidos.png", "Cobertura espacial del algoritmo"),
    ]:
        fig, ax = plt.subplots(figsize=(8.6, 5.5))
        bars = ax.bar(xc, seq[col].astype(float).to_numpy(), .55)
        ax.bar_label(bars, fmt="%.2f", padding=3)
        ax.set_xticks(xc, labels)
        ax.set_ylabel(unit)
        ax.set_title(f"{title} | Adirondack Quarter")
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
        ax.set_ylim(0, float(seq[col].max()) * 1.19)
        save_fig(fig, folder / fname)

    if not strata.empty:
        fig, ax = plt.subplots(figsize=(9, 5.5))
        for i, d in enumerate((32, 64)):
            vals = []
            for grp in ("GT_0_32", "GT_32_64"):
                s = strata[(strata["d_max"] == d) & (strata["grupo_gt"] == grp)]["mae_px"]
                if len(s) != 1:
                    raise ValueError(f"Estratos GT faltantes: D{d} {grp}")
                vals.append(float(s.iloc[0]))
            bars = ax.bar(np.arange(2) + (i-.5)*.36, vals, .36, label=f"K7-D{d}")
            ax.bar_label(bars, fmt="%.2f", padding=2)
        ax.set_xticks(np.arange(2), ["GT [0,32)", "GT [32,64)"])
        ax.set_ylabel("MAE (píxeles)")
        ax.set_title("Error por intervalo GT | solo K7")
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
        ax.legend()
        save_fig(fig, folder / "t22_calidad_estratos_K7.png")


def main():
    full, run_paths = load_runs()
    summary = summarize(full)
    quality, strata, quality_paths = load_quality()
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path("results") / f"t22_K7_K15_D32_D64_{tag}"
    if out.exists():
        raise FileExistsError(f"La carpeta ya existe: {out}")
    plots = out / "figuras"
    plots.mkdir(parents=True)

    full.to_csv(out / "t22_mediciones_y_calentamientos.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out / "t22_resumen_rendimiento.csv", index=False, encoding="utf-8-sig")
    quality.to_csv(out / "t22_resumen_calidad.csv", index=False, encoding="utf-8-sig")
    if not strata.empty:
        strata.to_csv(out / "t22_calidad_por_rango_gt_K7.csv", index=False, encoding="utf-8-sig")
    charts(summary, full, quality, strata, plots)

    crossing = (summary.loc[summary["modalidad"] == "distribuido_lan", "speedup"] > 1).sum()
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                         text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        commit = "desconocido"
    all_sources = run_paths + quality_paths
    manifest = {
        "fecha_generacion": datetime.now().astimezone().isoformat(),
        "git_commit": commit,
        "dataset": "Adirondack Quarter derivado localmente del Full de Middlebury 2014",
        "regiones_hw": [[96, 160], [160, 256], [224, 352]],
        "ventanas": [7, 15], "d_max": [32, 64],
        "repeticiones": 10, "calentamientos": 1,
        "mediciones": int((~full["es_calentamiento"]).sum()),
        "calentamientos_registrados": int(full["es_calentamiento"].sum()),
        "resultados_agregados": len(summary),
        "archivos_png": len(list(plots.glob("*.png"))),
        "equivalencia": bool(full["equivalente"].all()),
        "configuraciones_LAN_con_speedup_mayor_a_1": int(crossing),
        "fuentes": [{"archivo": str(p), "sha256": checksum(p)} for p in all_sources],
        "limitaciones": [
            "Los tamaños 96x160/160x256/224x352 son recortes locales, no resoluciones oficiales Middlebury.",
            "La resolución Quarter y su referencia fueron derivadas localmente de Full.",
            "La comparación de calidad K7 frente a K15 usa máscaras válidas diferentes; no supone un dominio evaluable idéntico.",
            "Los estratos de calidad por rango GT corresponden solo a K7; no se extrapolan a K15.",
            "La eficiencia speedup/p solo es interpretable para procesos locales de un mismo equipo.",
            "Speedup local mayor que p puede aparecer por variabilidad/efectos de ejecución; no se censura ni se considera eficiencia física >100%.",
            "Las etapas LAN pueden solaparse; receive_wait no equivale a latencia de red y no se suma directamente a compute.",
            "Las modalidades se midieron en bloques fijos no contrabalanceados; posible confusión con deriva temporal.",
            "No se observó speedup LAN >1 en las doce configuraciones, lo que no descarta un cruce en otras condiciones.",
            "No incluye aún resolución Half ni variaciones de escena.",
        ],
    }
    (out / "t22_manifiesto.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    pointer = Path("results/t22_ultimo_v2.txt")
    pointer.write_text(str(out), encoding="utf-8")
    print("Consolidacion completada")
    print(f"Mediciones: {manifest['mediciones']} | Calentamientos: {manifest['calentamientos_registrados']}")
    print(f"Filas agregadas: {len(summary)} | Figuras: {manifest['archivos_png']}")
    print(f"Todas equivalentes: {manifest['equivalencia']}")
    print(f"Configuraciones LAN con speedup >1: {int(crossing)}")
    print(f"Carpeta: {out.resolve()}")


if __name__ == "__main__":
    main()
