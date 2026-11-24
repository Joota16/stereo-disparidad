"""Ejecutor para la matriz ROI de SAD."""
from __future__ import annotations

import argparse
from datetime import datetime
from multiprocessing import freeze_support
from pathlib import Path

from experiments.run_benchmark_grid import run_benchmark_grid
from src.common.io_utils import load_stereo_pair


def parse_sizes(text: str) -> list[tuple[int, int]]:
    """Convierte '96x160,160x256' en pares (alto, ancho)."""
    sizes: list[tuple[int, int]] = []
    for raw in text.split(","):
        chunk = raw.strip().lower().replace("×", "x")
        parts = chunk.split("x")
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(f"Tamaño inválido: {raw!r}; formato ALTOxANCHO")
        try:
            h, w = (int(part.strip()) for part in parts)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Tamaño no numérico: {raw!r}") from exc
        if h <= 0 or w <= 0:
            raise argparse.ArgumentTypeError("Cada dimensión debe ser positiva")
        sizes.append((h, w))
    if not sizes or len(set(sizes)) != len(sizes):
        raise argparse.ArgumentTypeError("Se requieren tamaños distintos")
    return sizes


def main() -> None:
    parser = argparse.ArgumentParser(description="ROI Middlebury: comparación SAD secuencial, P2, P4 y LAN")
    parser.add_argument("--resolution", choices=("Q", "H"), required=True)
    parser.add_argument("--k", type=int, choices=(7, 15), required=True)
    parser.add_argument("--d-max", type=int, choices=(32, 64), required=True)
    parser.add_argument("--sizes", type=parse_sizes, default=None,
                        help="Ej. 96x160,160x256,224x352. Predeterminado: tamaños del estudio")
    parser.add_argument("--top", type=int, default=None, help="Fila inicial de ROI; Q=100, H=200")
    parser.add_argument("--left", type=int, default=0, help="Columna inicial de ROI")
    parser.add_argument("--reps", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--connect", required=True,
                        help="Endpoint del worker físico, p. ej. tcp://192.168.1.96:5555")
    parser.add_argument("--output", type=Path, default=None,
                        help="Directorio NUEVO; si se omite se genera con marca temporal")
    args = parser.parse_args()

    sizes = args.sizes if args.sizes is not None else (
        [(96, 160), (160, 256), (224, 352)] if args.resolution == "Q" else [(192, 320)]
    )
    top = args.top if args.top is not None else (100 if args.resolution == "Q" else 200)
    if top < 0 or args.left < 0 or args.reps < 1 or args.warmup < 0:
        parser.error("--top/--left deben ser no negativos; --reps >= 1 y --warmup >= 0")
    if args.connect.startswith("tcp://127.0.0.1:") or args.connect.startswith("tcp://localhost:"):
        parser.error("Para el estudio LAN se requiere un trabajador en otra computadora")
    if not args.connect.startswith("tcp://"):
        parser.error("--connect debe indicar un endpoint ZeroMQ tcp://...")

    data_dir = Path("data/raw") / f"Adirondack_{args.resolution}"
    left_image, right_image = load_stereo_pair(data_dir / "im0.png", data_dir / "im1.png")
    image_h, image_w = left_image.shape
    grid = []
    for h, w in sizes:
        if top + h > image_h or args.left + w > image_w:
            parser.error(f"ROI {h}x{w} fuera de la imagen {image_h}x{image_w} "
                         f"desde fila={top}, columna={args.left}")
        roi = (slice(top, top + h), slice(args.left, args.left + w))
        grid.append({
            "name": f"Adirondack_{args.resolution} (ROI {h}x{w})",
            "K": args.k,
            "d_min": 0,
            "d_max": args.d_max,
            "left": left_image[roi].copy(),
            "right": right_image[roi].copy(),
        })

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output = args.output or (
        Path("results") / f"roi_Adirondack_{args.resolution}_K{args.k}_D{args.d_max}_{stamp}"
    )
    # No crear salidas antes de comprobar que la carpeta no contiene evidencias.
    if output.exists() and any(output.iterdir()):
        parser.error(f"La carpeta ya contiene archivos: {output}")
    print(f"Escena: Adirondack_{args.resolution} | K={args.k} | D=[0,{args.d_max})")
    print(f"ROI: {sizes} | origen (fila,col)=({top},{args.left})")
    print(f"Repeticiones={args.reps}, calentamientos={args.warmup}, worker={args.connect}")
    print(f"Directorio: {output}", flush=True)
    run_benchmark_grid(
        grid_configs=grid,
        modes=["secuencial", "multiproceso_p2", "multiproceso_p4", "distribuido"],
        reps=args.reps,
        warmup=args.warmup,
        endpoint=args.connect,
        output_runs_csv=str(output / "runs.csv"),
        output_summary_csv=str(output / "summary.csv"),
    )
    print(f"BENCHMARK COMPLETO: {output}", flush=True)


if __name__ == "__main__":
    freeze_support()
    main()
