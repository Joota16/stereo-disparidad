"""Evaluacion de calidad estéreo, mapas de error y mapas de profundidad."""

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np

from src.common.io_utils import load_stereo_pair, read_calib, read_pfm, save_disparity_colormap
from src.common.metrics import evaluate_disparity
from src.parallel.multiprocess import compute_disparity_parallel
from src.stereo.sad import compute_sad


def disparity_to_depth(
    disparity: np.ndarray,
    baseline_mm: float,
    focal_px: float,
    doffs_px: float = 0.0,
    valid_mask: np.ndarray = None,
) -> np.ndarray:
    """
    Convierte mapa de disparidad a mapa de profundidad Z (en milimetros).
    Formula estandar Middlebury 2014: Z = (baseline * focal) / (d + doffs).
    """
    depth = np.full(disparity.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(disparity) & (disparity >= 0)
    if valid_mask is not None:
        valid = valid & valid_mask

    denom = disparity[valid] + doffs_px
    positive_denom = denom > 1e-4
    valid_indices = np.where(valid)

    selected_y = valid_indices[0][positive_denom]
    selected_x = valid_indices[1][positive_denom]

    depth[selected_y, selected_x] = (baseline_mm * focal_px) / denom[positive_denom]
    return depth


def save_depth_colormap(depth_map: np.ndarray, output_path: str, max_depth_m: float = 5.0):
    """Guarda mapa de profundidad en paleta de color TURBO normalizada en metros."""
    depth_m = depth_map / 1000.0  # mm a metros
    valid = np.isfinite(depth_m) & (depth_m > 0) & (depth_m <= max_depth_m)

    norm = np.zeros(depth_map.shape, dtype=np.uint8)
    if np.any(valid):
        d_vals = depth_m[valid]
        min_d, max_d = float(np.min(d_vals)), float(np.max(d_vals))
        if max_d > min_d:
            norm[valid] = ((depth_m[valid] - min_d) / (max_d - min_d) * 255.0).astype(np.uint8)

    colored = cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)
    colored[~valid] = [0, 0, 0]

    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(p), colored)


def ground_truth_range_coverage(ground_truth: np.ndarray, d_min: int, d_max: int) -> float:
    """Porcentaje de GT valido con disparidades en [d_min, d_max)."""
    if d_max <= d_min:
        raise ValueError("d_max debe ser mayor que d_min")
    valid = np.isfinite(ground_truth) & (ground_truth >= 0)
    total = int(np.count_nonzero(valid))
    if total == 0:
        raise ValueError("Ground truth sin pixeles validos no negativos")
    covered = int(np.count_nonzero(
        valid & (ground_truth >= d_min) & (ground_truth < d_max)
    ))
    return 100.0 * covered / total


def run_quality_evaluation(
    data_dir: str = "data/raw/Adirondack_Q",
    gt_path: str = "data/ground_truth/Adirondack_Q/disp0.pfm",
    out_dir: str = "results/t20_quality",
    d_max: int = 32,
    windows: List[int] = None,
) -> List[Dict[str, Any]]:
    if windows is None:
        windows = [5, 9]
    if not windows or any(k < 1 or k % 2 == 0 for k in windows):
        raise ValueError("Se requiere al menos una ventana impar positiva")
    if d_max <= 0:
        raise ValueError("d_max debe ser positivo")

    data_path = Path(data_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Cargar imagenes y calibracion
    left, right = load_stereo_pair(str(data_path / "im0.png"), str(data_path / "im1.png"))
    gt_disp = read_pfm(gt_path)

    # Validacion estricta de dimensiones sin escalado implicito
    if gt_disp.shape != left.shape:
        raise ValueError(
            f"Discrepancia de dimensiones: imagen {left.shape} vs Ground Truth {gt_disp.shape}. "
            "Se exige que ambos conjuntos provengan de la misma resolucion derivada documentada."
        )

    # Calibracion: utilizar directamente los valores provistos en el archivo asociado
    calib = read_calib(str(data_path / "calib.txt"))
    baseline = float(calib.get("baseline", 176.252))
    focal = float(calib.get("cam0", np.eye(3))[0, 0])
    doffs = float(calib.get("doffs", 0.0))

    # Analisis del rango de Ground Truth y cobertura
    gt_valid = gt_disp[np.isfinite(gt_disp) & (gt_disp >= 0)]
    gt_min = float(np.min(gt_valid)) if gt_valid.size > 0 else 0.0
    gt_max = float(np.max(gt_valid)) if gt_valid.size > 0 else 1.0

    # Guardar referencia visual de Ground Truth
    save_disparity_colormap(gt_disp, str(out_path / "disparidad_ground_truth.png"))
    gt_depth = disparity_to_depth(gt_disp, baseline, focal, doffs)
    save_depth_colormap(gt_depth, str(out_path / "profundidad_ground_truth.png"))

    # 2. Generar casos dinamicamente a partir de los parametros
    cases = []
    for K in windows:
        cases.append({"K": K, "d_min": 0, "d_max": d_max, "modo": "secuencial"})
    cases.append({"K": windows[0], "d_min": 0, "d_max": d_max, "modo": "multiproceso_p4"})

    records = []

    print("==================================================================================")
    print(" EVALUACION DE CALIDAD Y PRECISION ESTÉREO - GROUND TRUTH")
    print(f" Rango de disparidad GT: [{gt_min:.2f}, {gt_max:.2f}] px | Pixeles validos GT: {gt_valid.size}")
    print("==================================================================================")

    for c in cases:
        K = c["K"]
        dm = c["d_max"]
        mode = c["modo"]
        nombre = f"SAD_K{K}_D{dm}_{mode}"

        # Cobertura del rango de busqueda respecto al rango de la verdad de terreno
        coverage_pct = round(ground_truth_range_coverage(gt_disp, c["d_min"], dm), 2)

        print(f"\n--- Evaluando {nombre} (K={K}, D=[{c['d_min']}, {dm}]) | Cobertura GT: {coverage_pct}% ---")

        if mode == "secuencial":
            disp, mask = compute_sad(left, right, K, c["d_min"], dm)
        else:
            disp, mask = compute_disparity_parallel(left, right, K, c["d_min"], dm, workers=4)

        metrics = evaluate_disparity(
            disp, mask, gt_disp,
            gt_mask=np.isfinite(gt_disp) & (gt_disp >= 0), threshold=1.0
        )
        depth = disparity_to_depth(disp, baseline, focal, doffs, valid_mask=mask)

        # Guardar visualizaciones con nombres unicos y dinamicos
        slug = nombre.lower()
        save_disparity_colormap(disp, str(out_path / f"disp_{slug}.png"), valid_mask=mask)
        save_depth_colormap(depth, str(out_path / f"depth_{slug}.png"))

        err_map = metrics["error_map"]
        save_disparity_colormap(err_map, str(out_path / f"error_map_{slug}.png"), valid_mask=np.isfinite(err_map))

        bad_mask = np.zeros(disp.shape, dtype=np.uint8)
        bad_pixels = np.isfinite(err_map) & (err_map > 1.0)
        bad_mask[bad_pixels] = 255
        cv2.imwrite(str(out_path / f"bad_pixels_{slug}.png"), bad_mask)

        row = {
            "configuracion": nombre,
            "ventana_K": K,
            "d_min": c["d_min"],
            "d_max": dm,
            "modalidad": mode,
            "cobertura_rango_gt_pct": coverage_pct,
            "gt_min_px": round(gt_min, 2),
            "gt_max_px": round(gt_max, 2),
            "mae_epe_px": round(metrics["mae"], 4),
            "rmse_px": round(metrics["rmse"], 4),
            "bad_pixel_ratio_pct": round(metrics["bad_pixel_ratio"], 2),
            "invalid_ratio_pct": round(metrics["invalid_ratio"], 2),
            "pixeles_evaluados": metrics["evaluated_pixels"],
        }
        records.append(row)

        print(f"  MAE (End-Point Error): {metrics['mae']:.4f} px")
        print(f"  RMSE: {metrics['rmse']:.4f} px")
        print(f"  Bad-Pixel Ratio (error > 1.0 px): {metrics['bad_pixel_ratio']:.2f}%")
        print(f"  Pixeles invalidos (bordes/halo): {metrics['invalid_ratio']:.2f}%")

    # 3. Exportar tabla CSV
    csv_file = out_path / "t20_metricas_calidad.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    print(f"\n==========================================================================================================")
    print(f" TABLA COMPARATIVA DE CALIDAD (Guardada en {csv_file})")
    print("==========================================================================================================")
    print(f"{'Configuracion':<30} | {'Cobertura GT':<12} | {'MAE (px)':<9} | {'RMSE (px)':<10} | {'Bad Pixels (%)':<15} | {'Invalid (%)':<12}")
    print("-" * 106)
    for r in records:
        print(f"{r['configuracion']:<30} | {r['cobertura_rango_gt_pct']:<10.1f} % | {r['mae_epe_px']:<9.4f} | {r['rmse_px']:<10.4f} | {r['bad_pixel_ratio_pct']:<15.2f} | {r['invalid_ratio_pct']:<12.2f}")
    print("==========================================================================================================")
    return records


def main():
    parser = argparse.ArgumentParser(description="Evaluacion de calidad estéreo y mapas de error ")
    parser.add_argument("--data-dir", default="data/raw/Adirondack_Q")
    parser.add_argument("--gt", default="data/ground_truth/Adirondack_Q/disp0.pfm")
    parser.add_argument("--output", default="results/t20_quality")
    parser.add_argument("--d-max", type=int, default=32)
    parser.add_argument("--windows", nargs="+", type=int, default=[5, 9])
    args = parser.parse_args()

    run_quality_evaluation(args.data_dir, args.gt, args.output, args.d_max, args.windows)


if __name__ == "__main__":
    main()
