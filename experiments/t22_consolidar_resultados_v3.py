"""Consolidacion final de resultados experimentales Quarter y Half."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from experiments import t22_consolidar_resultados_v2 as prev

HALF_POINTER = Path("results/t21_ultimo_Half_K15_D64_10rep.txt")
MASK_PATTERN = "t20_mascara_comun_*/comparacion.csv"
GROUPS = ("Global", "GT_0_32", "GT_32_64")


def load_half() -> tuple[pd.DataFrame, Path]:
    path = prev.source_runs(str(HALF_POINTER))
    raw = pd.read_csv(path)
    required = set(prev.GROUP + ["tiempo_s", "equivalente", "es_calentamiento", "tipo_conexion"])
    if required - set(raw.columns):
        raise ValueError(f"{path}: faltan columnas {sorted(required - set(raw.columns))}")
    for c in ("alto", "ancho", "ventana_K", "d_min", "d_max"):
        raw[c] = pd.to_numeric(raw[c], errors="raise").astype(int)
    if not ((raw["alto"] == 192) & (raw["ancho"] == 320) &
            (raw["ventana_K"] == 15) & (raw["d_min"] == 0) &
            (raw["d_max"] == 64) & raw["caso"].astype(str).str.startswith("Adirondack_H")).all():
        raise ValueError(f"{path}: configuración Half no coincide con ROI 192x320, K15, D64")
    if set(raw["modalidad"]) != set(prev.MODES):
        raise ValueError(f"{path}: arquitecturas incompletas o inesperadas")
    if not (raw.loc[raw["modalidad"] == "distribuido_lan", "tipo_conexion"] == "lan_remota").all():
        raise ValueError("La modalidad Half distribuida no está registrada como LAN remota")
    raw["equivalente"] = prev.boolean(raw["equivalente"], "equivalente")
    raw["es_calentamiento"] = prev.boolean(raw["es_calentamiento"], "es_calentamiento")
    raw["tiempo_s"] = pd.to_numeric(raw["tiempo_s"], errors="raise")
    if not raw["equivalente"].all() or not (np.isfinite(raw["tiempo_s"]) & (raw["tiempo_s"] > 0)).all():
        raise ValueError("Half: tiempos inválidos o ejecuciones no equivalentes")
    measured, warm = raw.loc[~raw["es_calentamiento"]], raw.loc[raw["es_calentamiento"]]
    for subset, expected in ((measured, 10), (warm, 1)):
        counts = subset.groupby(prev.GROUP).size()
        if len(counts) != 4 or not (counts == expected).all():
            raise ValueError(f"Half: esperadas cuatro modalidades con {expected} ejecuciones cada una")
    if len(raw) != 44:
        raise ValueError("Half: se esperan 40 medidas + 4 calentamientos")
    raw["fuente"] = str(path)
    raw["experimento"] = "Half_K15_D64"
    return raw, path


def load_common_mask() -> tuple[pd.DataFrame, Path]:
    candidates = sorted(Path("results").glob(MASK_PATTERN), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError("Falta results/t20_mascara_comun_*/comparacion.csv")
    path = candidates[0]
    df = pd.read_csv(path)
    keys = ["K", "d_max", "grupo_gt"]
    cols = keys + ["pixeles_evaluados", "mae_px", "rmse_px", "bad_pixels_pct"]
    if set(cols) - set(df.columns):
        raise ValueError(f"{path}: faltan columnas {sorted(set(cols)-set(df.columns))}")
    if len(df) != 12 or df.duplicated(keys).any():
        raise ValueError(f"{path}: se esperan exactamente 12 combinaciones únicas")
    for c in ("K", "d_max", "pixeles_evaluados"):
        df[c] = pd.to_numeric(df[c], errors="raise").astype(int)
    for c in ("mae_px", "rmse_px", "bad_pixels_pct"):
        df[c] = pd.to_numeric(df[c], errors="raise")
    expected = {(k, d, grp) for k in (7, 15) for d in (32, 64) for grp in GROUPS}
    actual = set(df[keys].itertuples(index=False, name=None))
    if actual != expected:
        raise ValueError(f"{path}: combinaciones K/D/grupo incompletas")
    if not np.isfinite(df[["mae_px", "rmse_px", "bad_pixels_pct"]].to_numpy()).all():
        raise ValueError("Las métricas de máscara común deben ser finitas")
    if not df["bad_pixels_pct"].between(0, 100).all():
        raise ValueError("Bad Pixels fuera de 0-100%")
    n = df.pivot_table(index=["K", "d_max"], columns="grupo_gt", values="pixeles_evaluados", aggfunc="first")
    if not (n["Global"] == n["GT_0_32"] + n["GT_32_64"]).all():
        raise ValueError("Los recuentos estratificados no suman el recuento global")
    if n.nunique().max() != 1 or (df["pixeles_evaluados"] <= 0).any():
        raise ValueError("Las cuatro configuraciones no comparten idénticos tamaños de máscara")
    return df.sort_values(keys).reset_index(drop=True), path


def charts_half(half_summary: pd.DataFrame, plots: Path) -> None:
    q = half_summary.set_index("modalidad")
    modes = list(prev.MODES)
    labels = [prev.MODE_LABELS[m] for m in modes]
    for metric, ylabel, title, filename in (
        ("mediana_s", "Tiempo mediano (s)", "Half 192×320 | K15, D64 | n=10", "t22_Half_tiempos.png"),
        ("speedup", "Speedup frente a secuencial (×)", "Half 192×320 | aceleración", "t22_Half_speedup.png"),
    ):
        vals = [float(q.loc[m, metric]) for m in modes]
        fig, ax = plt.subplots(figsize=(9, 5.5))
        bars = ax.bar(np.arange(4), vals, width=.6)
        ax.bar_label(bars, fmt="%.3f", padding=3)
        ax.set_xticks(np.arange(4), labels)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_ylim(0, max(vals)*1.22)
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
        if metric == "speedup":
            ax.axhline(1, linestyle="--", linewidth=1.2, label="Referencia secuencial 1×")
            ax.legend()
        prev.save_fig(fig, plots / filename)


def charts_mask(df: pd.DataFrame, plots: Path) -> None:
    configs = [(7,32),(7,64),(15,32),(15,64)]
    names = [f"K{k}–D{d}" for k,d in configs]
    global_df = df[df["grupo_gt"] == "Global"].set_index(["K", "d_max"])
    for col, suffix, title, filename in (
        ("mae_px", "MAE (px)", "MAE con máscara común", "t22_mascara_comun_MAE.png"),
        ("bad_pixels_pct", "Bad Pixels (%)", "Bad Pixels con máscara común", "t22_mascara_comun_bad_pixels.png"),
    ):
        vals = [float(global_df.loc[(k,d),col]) for k,d in configs]
        fig, ax = plt.subplots(figsize=(9,5.5))
        bars = ax.bar(np.arange(4),vals,.6)
        ax.bar_label(bars,fmt="%.2f",padding=2)
        ax.set_xticks(np.arange(4),names)
        ax.set_ylabel(suffix)
        ax.set_title(title + " | 332,812 píxeles comunes")
        ax.grid(axis="y",alpha=.2)
        ax.set_axisbelow(True)
        ax.set_ylim(0,max(vals)*1.17)
        prev.save_fig(fig,plots/filename)
    fig, ax = plt.subplots(figsize=(10.5,5.6))
    groups = ("GT_0_32","GT_32_64")
    for i,(k,d) in enumerate(configs):
        vals = [float(df[(df["K"]==k)&(df["d_max"]==d)&(df["grupo_gt"]==g)]["mae_px"].iloc[0]) for g in groups]
        x=np.arange(2)+(i-1.5)*.19
        bars=ax.bar(x,vals,.19,label=f"K{k}–D{d}")
        ax.bar_label(bars,fmt="%.1f",fontsize=8,padding=2)
    ax.set_xticks(np.arange(2),["GT [0,32)","GT [32,64)"])
    ax.set_ylabel("MAE (px)")
    ax.set_title("Comparación en grupos GT sobre la misma máscara de evaluación")
    ax.grid(axis="y",alpha=.2)
    ax.set_axisbelow(True)
    ax.legend(ncol=2)
    prev.save_fig(fig,plots/"t22_mascara_comun_estratos.png")


def main() -> None:
    quarter, q_sources = prev.load_runs()
    half, half_path = load_half()
    full = pd.concat([quarter, half], ignore_index=True)
    if len(full) != 572 or int((~full["es_calentamiento"]).sum()) != 520:
        raise AssertionError("Se esperan 520 mediciones, 52 calentamientos")
    summary = prev.summarize(quarter)
    # El resumen se calcula con 48 grupos Quarter y 4 grupos Half; no simular regiones.
    measured = half.loc[~half["es_calentamiento"]]
    h_summary = measured.groupby(prev.GROUP, sort=True)["tiempo_s"].agg(
        repeticiones="count",media_s="mean",mediana_s="median",
        desv_std_s=lambda s: float(np.std(s.to_numpy(), ddof=0)),
        minimo_s="min",maximo_s="max").reset_index()
    base = float(h_summary.loc[h_summary["modalidad"]=="secuencial","mediana_s"].iloc[0])
    h_summary["mediana_base_s"] = base
    h_summary["speedup"] = base / h_summary["mediana_s"]
    h_summary["eficiencia_local"] = np.nan
    h_summary.loc[h_summary["modalidad"]=="secuencial","eficiencia_local"] = 1.0
    for mode,p in (("multiproceso_p2",2),("multiproceso_p4",4)):
        s=h_summary["modalidad"]==mode
        h_summary.loc[s,"eficiencia_local"]=h_summary.loc[s,"speedup"]/p
    h_summary["pixeles"] = h_summary["alto"]*h_summary["ancho"]
    summary_all = pd.concat([summary,h_summary],ignore_index=True)
    if len(summary_all)!=52 or not (summary_all["repeticiones"]==10).all():
        raise AssertionError("Se esperan 52 filas resumen, cada una con diez repeticiones")

    quality, strata, q_sources_quality = prev.load_quality()
    common, common_path = load_common_mask()
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path("results") / f"t22_cierre_Quarter_Half_{tag}"
    if out.exists():
        raise FileExistsError(f"Ya existe {out}")
    plots = out / "figuras"
    plots.mkdir(parents=True, exist_ok=False)

    full.to_csv(out/"t22_mediciones_y_calentamientos.csv",index=False,encoding="utf-8-sig")
    summary_all.to_csv(out/"t22_resumen_rendimiento_Quarter_Half.csv",index=False,encoding="utf-8-sig")
    quality.to_csv(out/"t22_calidad_original.csv",index=False,encoding="utf-8-sig")
    common.to_csv(out/"t22_calidad_mascara_comun.csv",index=False,encoding="utf-8-sig")
    if not strata.empty:
        strata.to_csv(out/"t22_calidad_estratos_K7_original.csv",index=False,encoding="utf-8-sig")
    prev.charts(summary,quarter,quality,strata,plots)
    charts_half(h_summary,plots)
    charts_mask(common,plots)

    sources = q_sources+[half_path]+q_sources_quality+[common_path]
    try:
        commit=subprocess.check_output(["git","rev-parse","HEAD"],text=True,stderr=subprocess.DEVNULL).strip()
    except Exception:
        commit="desconocido"
    crossing = int(((summary_all["modalidad"]=="distribuido_lan") & (summary_all["speedup"]>1)).sum())
    manifest={
        "fecha":datetime.now().astimezone().isoformat(),
        "git_commit":commit,
        "resoluciones":{
            "Quarter":"derivada localmente del Middlebury 2014 Full; tres ROI 96×160,160×256,224×352; K7/K15; D32/D64",
            "Half":"derivada localmente del Middlebury 2014 Full; ROI 192×320; K15; D64"
        },
        "mediciones":int((~full["es_calentamiento"]).sum()),
        "calentamientos":int(full["es_calentamiento"].sum()),
        "filas_resumen":len(summary_all),
        "calidad_mascara_comun_filas":len(common),
        "calidad_mascara_comun_pixeles":int(common.loc[common["grupo_gt"]=="Global","pixeles_evaluados"].iloc[0]),
        "figuras":len(list(plots.glob("*.png"))),
        "equivalencia_exacta":bool(full["equivalente"].all()),
        "lan_speedup_mayor_a_1":crossing,
        "fuentes":[{"archivo":str(p),"sha256":prev.checksum(p)} for p in sources],
        "limitaciones":[
            "Half se midio solo en una ROI K15-D64, sin matriz factorial completa; no se atribuyen diferencias solo a la resolucion.",
            "Quarter y Half fueron derivados localmente de Full de Middlebury 2014; no son los conjuntos Q/H oficiales.",
            "Las 12 configuraciones Quarter y la unica Half usan regiones de interes, no imagenes completas.",
            "Las metricas de calidad global sin mascara comun y con mascara comun responden a poblaciones evaluables distintas.",
            "Para comparar ventanas K7 y K15 se deben citar las metricas calculadas con mascara comun de 332,812 pixeles.",
            "La eficiencia speedup/p corresponde solo a procesos de la misma PC; el cluster heterogeneo LAN lleva N/A.",
            "Una eficiencia aparente superior a 100% en P2 no se interpreta como eficiencia fisica real.",
            "Las duraciones locales y remotas se solapan y no deben sumarse; espera de recepcion no es latencia pura de red.",
            "Los modos se ejecutaron en bloques de orden fijo; deriva temporal y condiciones de carga pueden afectar los tiempos.",
            "No se observo un cruce favorable a LAN en las configuraciones medidas; no se extrapola a otras cargas o equipos.",
            "La metadata automatica del benchmark corresponde al maestro; registrar por separado hardware y condiciones del worker.",
            "En Half D64 no cubre todo el rango GT valido de la escena; Half se uso solo para medir rendimiento.",
        ],
    }
    (out/"t22_manifiesto.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (Path("results")/"t22_ultimo_v3.txt").write_text(str(out),encoding="utf-8")
    print("Consolidacion completada")
    print(f"Mediciones: {manifest['mediciones']} | Calentamientos: {manifest['calentamientos']}")
    print(f"Filas resumen: {manifest['filas_resumen']} | Calidad común: {manifest['calidad_mascara_comun_filas']}")
    print(f"Figuras: {manifest['figuras']} | Eq: {manifest['equivalencia_exacta']} | Cruces LAN > 1: {crossing}")
    print(f"Resultados: {out.resolve()}")

if __name__ == "__main__":
    main()
