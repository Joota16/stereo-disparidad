"""
Script para validar la salida secuencial frente al ground truth (T10).
Genera mapa de error, métricas MAE/RMSE y visualizaciones.
"""

from pathlib import Path
import argparse
import numpy as np

from src.common.io_utils import load_stereo_pair, read_pfm, save_disparity_colormap
from src.common.metrics import evaluate_disparity
from src.stereo.sad import compute_sad


def run_sequential_validation(left_path, right_path, gt_path, window_size=9, d_min=0, d_max=70, output_dir="results/t10_validation"):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Cargando par estéreo:\n- Izquierda: {left_path}\n- Derecha: {right_path}")
    left_gray, right_gray = load_stereo_pair(left_path, right_path)

    print(f"Ejecutando algoritmo SAD secuencial (K={window_size}, D=[{d_min}, {d_max}))...")
    disp_pred, valid_mask = compute_sad(left_gray, right_gray, window_size, d_min, d_max)

    print(f"Cargando ground truth desde {gt_path}...")
    gt = read_pfm(gt_path)

    print("Calculando métricas de exactitud...")
    metrics = evaluate_disparity(disp_pred, valid_mask, gt)

    print("\n" + "=" * 40)
    print("RESULTADOS DE VALIDACIÓN FRENTE A GROUND TRUTH (T10)")
    print("=" * 40)
    print(f"Total píxeles:          {metrics['total_pixels']}")
    print(f"Píxeles evaluados:      {metrics['evaluated_pixels']} ({metrics['evaluated_pixels'] / metrics['total_pixels'] * 100:.2f}%)")
    print(f"Píxeles inválidos:      {metrics['invalid_ratio']:.2f}%")
    print(f"MAE (End-Point Error):  {metrics['mae']:.4f} px")
    print(f"RMSE de disparidad:     {metrics['rmse']:.4f} px")
    print(f"Bad-Pixel Ratio (>1px): {metrics['bad_pixel_ratio']:.2f}%")
    print("=" * 40)

    # Exportar visualizaciones
    pred_vis_path = out_dir / "disparidad_secuencial.png"
    err_vis_path = out_dir / "mapa_error.png"

    save_disparity_colormap(disp_pred, pred_vis_path, valid_mask=valid_mask)
    save_disparity_colormap(metrics["error_map"], err_vis_path, valid_mask=valid_mask)

    print(f"\nVisualizaciones guardadas:")
    print(f"- Mapa de disparidad: {pred_vis_path}")
    print(f"- Mapa de error:       {err_vis_path}")

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validacion T10 de SAD secuencial frente a Ground Truth")
    parser.add_argument("--left", default="data/raw/adirondack_Q/im0.png")
    parser.add_argument("--right", default="data/raw/adirondack_Q/im1.png")
    parser.add_argument("--gt", default="data/ground_truth/adirondack_Q/disp0.pfm")
    parser.add_argument("--window", type=int, default=9)
    parser.add_argument("--dmin", type=int, default=0)
    parser.add_argument("--dmax", type=int, default=70)
    parser.add_argument("--out", default="results/t10_validation")
    args = parser.parse_args()

    run_sequential_validation(args.left, args.right, args.gt, args.window, args.dmin, args.dmax, args.out)
