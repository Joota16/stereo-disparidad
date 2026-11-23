import csv
from pathlib import Path

import numpy as np

from src.common.io_utils import load_stereo_pair, read_pfm
from src.common.metrics import evaluate_disparity
from src.stereo.sad import compute_sad


def main():
    left, right = load_stereo_pair(
        "data/raw/Adirondack_Q/im0.png",
        "data/raw/Adirondack_Q/im1.png"
    )
    gt = read_pfm("data/ground_truth/Adirondack_Q/disp0.pfm")

    valid_gt = np.isfinite(gt) & (gt >= 0)

    grupos = {
        "GT_0_32": valid_gt & (gt < 32),
        "GT_32_64": valid_gt & (gt >= 32) & (gt < 64),
    }

    resultados = []

    for d_max in [32, 64]:
        print(f"Calculando SAD K7 D{d_max}...", flush=True)
        disparidad, mascara = compute_sad(
            left, right, 7, 0, d_max
        )

        for nombre, gt_mask in grupos.items():
            metricas = evaluate_disparity(
                disparidad,
                mascara,
                gt,
                gt_mask=gt_mask,
                threshold=1.0
            )

            resultados.append({
                "d_max": d_max,
                "grupo_gt": nombre,
                "pixeles_gt_grupo": int(np.count_nonzero(gt_mask)),
                "pixeles_evaluados": metricas["evaluated_pixels"],
                "mae_px": round(metricas["mae"], 4),
                "rmse_px": round(metricas["rmse"], 4),
                "bad_pixels_pct": round(
                    metricas["bad_pixel_ratio"], 2
                ),
            })

    salida = Path("results/t20_analisis_por_rango")
    salida.mkdir(parents=True, exist_ok=True)
    archivo = salida / "metricas_estratificadas.csv"

    if archivo.exists():
        raise FileExistsError(
            "Ya existe el resultado. Conservar la evidencia anterior."
        )

    with archivo.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(resultados[0].keys())
        )
        writer.writeheader()
        writer.writerows(resultados)

    print(f"Resultados guardados en: {archivo}")


if __name__ == "__main__":
    main()
