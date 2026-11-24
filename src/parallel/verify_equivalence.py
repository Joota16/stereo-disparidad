"""Verifica la equivalencia numerica exacta entre la version secuencial y multiproceso."""

from pathlib import Path
import argparse
import numpy as np

from src.common.io_utils import load_stereo_pair, save_disparity_colormap
from src.stereo.sad import compute_sad
from src.parallel.multiprocess import compute_disparity_parallel


def check_sequential_parallel_equivalence(
    left_path,
    right_path,
    window_sizes=(5, 9),
    d_max_list=(16, 32),
    workers_list=(2, 4),
    output_dir="results/t13_equivalence",
):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    left_gray, right_gray = load_stereo_pair(left_path, right_path)
    height, width = left_gray.shape

    print("=" * 65)
    print("VERIFICACION DE EQUIVALENCIA: SECUENCIAL VS MULTIPROCESO")
    print(f"Dimensiones de imagen: {width}x{height}")
    print("=" * 65)

    all_passed = True
    total_comparisons = 0

    for window_size in window_sizes:
        for d_max in d_max_list:
            # 1. Ejecutar linea base secuencial
            disp_seq, mask_seq = compute_sad(
                left_gray, right_gray, window_size=window_size, d_min=0, d_max=d_max
            )

            for workers in workers_list:
                total_comparisons += 1
                # 2. Ejecutar paralelo con N trabajadores
                disp_par, mask_par = compute_disparity_parallel(
                    left_gray,
                    right_gray,
                    window_size=window_size,
                    d_min=0,
                    d_max=d_max,
                    workers=workers,
                )

                # 3. Comprobar igualdad estricta de mascaras booleanas
                mask_equal = np.array_equal(mask_seq, mask_par)

                # 4. Comprobar igualdad en pixeles evaluados como validos
                both_valid = mask_seq & mask_par
                if np.sum(both_valid) > 0:
                    max_diff = float(np.max(np.abs(disp_seq[both_valid] - disp_par[both_valid])))
                else:
                    max_diff = 0.0

                # 5. Comprobar que en pixeles invalidos ambos sean NaN
                invalid_seq = ~mask_seq
                invalid_par = ~mask_par
                nan_match = np.all(np.isnan(disp_seq[invalid_seq])) and np.all(
                    np.isnan(disp_par[invalid_par])
                )

                passed = mask_equal and (max_diff == 0.0) and nan_match
                all_passed = all_passed and passed

                status = "PASÓ (EXACTO)" if passed else "FALLÓ"
                print(
                    f"K={window_size:2d} | D_max={d_max:2d} | {workers} workers -> "
                    f"Diff Max: {max_diff:.6f} px | Máscara: {mask_equal} | {status}"
                )

    print("=" * 65)
    if all_passed:
        print(f"RESULTADO FINAL: ÉXITO TOTAL ({total_comparisons}/{total_comparisons} pruebas pasaron).")
        print("El paralelismo multiproceso NO altera el resultado numérico.")
    else:
        print("RESULTADO FINAL: Se detectaron discrepancias entre versiones.")
    print("=" * 65)

    # Exportar mapas comparativos de muestra
    save_disparity_colormap(disp_seq, out_dir / "disparidad_secuencial_ejemplo.png", valid_mask=mask_seq)
    save_disparity_colormap(disp_par, out_dir / "disparidad_paralelo_ejemplo.png", valid_mask=mask_par)
    print(f"Mapas guardados en: {out_dir}")

    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verificacion de equivalencia secuencial vs multiproceso")
    parser.add_argument("--left", default="data/raw/adirondack_Q/im0.png")
    parser.add_argument("--right", default="data/raw/adirondack_Q/im1.png")
    parser.add_argument("--out", default="results/t13_equivalence")
    args = parser.parse_args()

    check_sequential_parallel_equivalence(args.left, args.right, output_dir=args.out)
