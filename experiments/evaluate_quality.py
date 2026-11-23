"""Evaluacion formal de calidad estéreo, mapas de error y mapas de profundidad (T20)."""

import argparse
import csv
from pathlib import Path

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
    valid = np.isfinite(disparity) & (disparity > 0)
    if valid_mask is not None:
        valid = valid & valid_mask

    denom = disparity[valid] + doffs_px
    positive_denom = denom > 1e-4
    valid_indices = np.where(valid)

    selected_y = valid_indices[0][positive_denom]
    selected_x = valid_indices[1][positive_denom]

    depth[selected_y, selected_x] = (baseline_mm * focal_px) / denom[positive_denom]
    return depth


def save_depth_colormap(depth_map: np.ndarray, output_path: str, max_depth_m: float = 4.0):
    """Guarda mapa de profundidad en paleta de color normalizada en metros."""
    depth_m = depth_map / 1000.0  # mm a metros
    valid = np.isfinite(depth_m) & (depth_m > 0) & (depth_m <= max_depth_m)

    norm = np.zeros(depth_map.shape, dtype=np.uint8)
    if np.any(valid):
        d_vals = depth_m[valid]
        min_d, max_d = float(np.min(d_vals)), float(np.max(d_vals))
        if max_d > min_d:
            norm[valid] = ((depth_m[valid] - min_d) / (max_d - min_d) * 255.0).astype(np.uint8)

    colored = cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)
    colored[~valid] = [0, 0, 0]  # negro en zonas sin profundidad

    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(p), colored)


def run_quality_evaluation(
    data_dir: str = "data/raw/adirondack_Q",
    gt_path: str = "data/ground_truth/adirondack_Q/disp0.pfm",
    out_dir: str = "results/t20_quality",
    d_max: int = 32,
):
    data_path = Path(data_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Cargar datos
    left, right = load_stereo_pair(str(data_path / "im0.png"), str(data_path / "im1.png"))
    gt_disp = read_pfm(gt_path)

    # Si la imagen fue escalada a Quarter, la disparidad GT se divide por el factor
    calib = read_calib(str(data_path / "calib.txt"))
    scale_factor = 4.0  # Quarter
    baseline = calib.get("baseline", 176.252)
    focal = calib.get("cam0", np.eye(3))[0, 0] / scale_factor
    doffs = calib.get("doffs", 0.0) / scale_factor

    # Ajustar resolucion de GT si difiere
    if gt_disp.shape != left.shape:
        gt_disp = cv2.resize(gt_disp, (left.shape[1], left.shape[0]), interpolation=cv2.INTER_NEAREST)
        gt_disp = gt_disp / scale_factor

    # Guardar referencia visual de Ground Truth
    save_disparity_colormap(gt_disp, str(out_path / "disparidad_ground_truth.png"))
    gt_depth = disparity_to_depth(gt_disp, baseline, focal, doffs)
    save_depth_colormap(gt_depth, str(out_path / "profundidad_ground_truth.png"))

    # 2. Configuraciones a evaluar
    cases = [
        {"nombre": "SAD_K5_D32_Secuencial", "K": 5, "d_min": 0, "d_max": d_max, "modo": "secuencial"},
        {"nombre": "SAD_K9_D32_Secuencial", "K": 9, "d_min": 0, "d_max": d_max, "modo": "secuencial"},
        {"nombre": "SAD_K5_D32_Multiproceso4", "K": 5, "d_min": 0, "d_max": d_max, "modo": "multiproceso"},
    ]

    records = []

    print("======================================================================")
    print(" EVALUACION DE CALIDAD Y PRECISION ESTÉREO (T20) - GROUND TRUTH")
    print("======================================================================")

    for c in cases:
        print(f"\n--- Evaluando {c['nombre']} (K={c['K']}, D=[{c['d_min']}, {c['d_max']}]) ---")
        if c["modo"] == "secuencial":
            disp, mask = compute_sad(left, right, c["K"], c["d_min"], c["d_max"])
        else:
            disp, mask = compute_disparity_parallel(left, right, c["K"], c["d_min"], c["d_max"], workers=4)

        metrics = evaluate_disparity(disp, mask, gt_disp, threshold=1.0)

        # Calculo de profundidad
        depth = disparity_to_depth(disp, baseline, focal, doffs, valid_mask=mask)

        # Guardar visualizaciones
        slug = c["nombre"].lower()
        save_disparity_colormap(disp, str(out_path / f"disp_{slug}.png"), valid_mask=mask)
        save_depth_colormap(depth, str(out_path / f"depth_{slug}.png"))

        # Mapa de error y mascara de bad pixels
        err_map = metrics["error_map"]
        save_disparity_colormap(err_map, str(out_path / f"error_map_{slug}.png"), valid_mask=np.isfinite(err_map))

        bad_mask = np.zeros(disp.shape, dtype=np.uint8)
        bad_pixels = np.isfinite(err_map) & (err_map > 1.0)
        bad_mask[bad_pixels] = 255
        cv2.imwrite(str(out_path / f"bad_pixels_{slug}.png"), bad_mask)

        row = {
            "configuracion": c["nombre"],
            "ventana_K": c["K"],
            "d_max": c["d_max"],
            "modo": c["modo"],
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

    print(f"\n======================================================================")
    print(f" TABLA COMPARATIVA DE CALIDAD (T20) (Guardada en {csv_file})")
    print("======================================================================")
    print(f"{'Configuracion':<28} | {'MAE (px)':<9} | {'RMSE (px)':<10} | {'Bad Pixels (%)':<15} | {'Invalid (%)':<12}")
    print("-" * 84)
    for r in records:
        print(f"{r['configuracion']:<28} | {r['mae_epe_px']:<9.4f} | {r['rmse_px']:<10.4f} | {r['bad_pixel_ratio_pct']:<15.2f} | {r['invalid_ratio_pct']:<12.2f}")
    print("======================================================================")


def main():
    parser = argparse.ArgumentParser(description="Evaluacion de calidad estéreo y mapas de error (T20)")
    parser.add_argument("--data-dir", default="data/raw/adirondack_Q")
    parser.add_argument("--gt", default="data/ground_truth/adirondack_Q/disp0.pfm")
    parser.add_argument("--output", default="results/t20_quality")
    parser.add_argument("--d-max", type=int, default=32)
    args = parser.parse_args()

    run_quality_evaluation(args.data_dir, args.gt, args.output, args.d_max)


if __name__ == "__main__":
    main()
