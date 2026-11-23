import csv
from datetime import datetime
from multiprocessing import freeze_support
from pathlib import Path

import numpy as np

from src.common.io_utils import load_stereo_pair, read_pfm
from src.parallel.multiprocess import compute_disparity_parallel


def main():
    left, right = load_stereo_pair(
        "data/raw/Adirondack_Q/im0.png",
        "data/raw/Adirondack_Q/im1.png"
    )
    gt = read_pfm("data/ground_truth/Adirondack_Q/disp0.pfm")

    predicciones = {}

    for K in [7, 15]:
        for D in [32, 64]:
            print(f"Calculando K={K}, D={D}...", flush=True)

            disp, mask = compute_disparity_parallel(
                left, right,
                window_size=K,
                d_min=0,
                d_max=D,
                workers=4
            )
            predicciones[(K, D)] = (disp, mask)

    # Misma mascara para las cuatro configuraciones.
    mascara_comun = np.isfinite(gt) & (gt >= 0)

    for _, mask in predicciones.values():
        mascara_comun &= mask

    grupos = {
        "Global": mascara_comun,
        "GT_0_32": mascara_comun & (gt < 32),
        "GT_32_64": mascara_comun & (gt >= 32) & (gt < 64),
    }

    registros = []

    for (K, D), (disp, _) in predicciones.items():
        for grupo, mascara in grupos.items():
            n = int(np.count_nonzero(mascara))

            if n == 0:
                raise ValueError(f"Grupo sin pixeles: {grupo}")

            errores = np.abs(
                disp[mascara].astype(np.float64) -
                gt[mascara].astype(np.float64)
            )

            registros.append({
                "K": K,
                "d_max": D,
                "grupo_gt": grupo,
                "pixeles_evaluados": n,
                "mae_px": round(float(np.mean(errores)), 4),
                "rmse_px": round(
                    float(np.sqrt(np.mean(errores ** 2))), 4
                ),
                "bad_pixels_pct": round(
                    float(np.mean(errores > 1.0) * 100), 2
                ),
            })

    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    salida = Path("results") / f"t20_mascara_comun_{fecha}"
    salida.mkdir(parents=True, exist_ok=False)

    archivo = salida / "comparacion.csv"

    with archivo.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(registros[0].keys())
        )
        writer.writeheader()
        writer.writerows(registros)

    print(f"\nPixeles con mascara comun: {np.count_nonzero(mascara_comun)}")
    print(f"Resultados: {archivo}")


if __name__ == "__main__":
    freeze_support()
    main()
