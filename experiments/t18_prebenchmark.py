"""T18: comparación exploratoria con métricas internas del maestro ZeroMQ."""

import argparse
import csv
from pathlib import Path
from statistics import median
from time import perf_counter

import numpy as np

from src.stereo.sad import compute_sad
from src.parallel.multiprocess import compute_disparity_parallel
from src.distributed.master import run_master


METRIC_KEYS = (
    "partition_seconds", "serialize_seconds", "socket_setup_seconds",
    "connect_call_seconds", "send_call_seconds", "local_compute_seconds",
    "receive_wait_seconds", "remote_compute_seconds",
    "response_decode_seconds", "merge_seconds",
    "total_seconds", "request_payload_bytes", "response_payload_bytes",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--connect", required=True)
    parser.add_argument("--height", type=int, default=95)
    parser.add_argument("--width", type=int, default=161)
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--output", default="results/t18_preliminar.csv")
    args = parser.parse_args()

    if args.height < 4 or args.width < 1 or args.reps < 1:
        parser.error("Dimensiones o repeticiones invalidas")

    rng = np.random.default_rng(2026)
    left = rng.integers(0, 256, size=(args.height, args.width), dtype=np.uint8)
    right = rng.integers(0, 256, size=(args.height, args.width), dtype=np.uint8)
    params = (5, 0, 8)
    reference, reference_mask = compute_sad(left, right, *params)
    modes = ["sequential", "parallel_2", "parallel_4", "distributed"]

    def execute(mode):
        if mode == "sequential":
            disp, mask = compute_sad(left, right, *params)
            return disp, mask, {}
        if mode.startswith("parallel_"):
            workers = int(mode.split("_")[1])
            disp, mask = compute_disparity_parallel(left, right, *params, workers)
            return disp, mask, {}
        return run_master({
            "left_gray": left,
            "right_gray": right,
            "window_size": 5,
            "d_min": 0,
            "d_max": 8,
            "connect": args.connect,
            "timeout_ms": 30000,
        })

    rows = []
    # Se descarta un calentamiento completo por modalidad.
    for repetition in range(-1, args.reps):
        for mode in modes:
            start = perf_counter()
            disp, mask, stats = execute(mode)
            wall_seconds = perf_counter() - start
            np.testing.assert_array_equal(mask, reference_mask)
            np.testing.assert_allclose(
                disp, reference, rtol=0, atol=0, equal_nan=True
            )
            if repetition >= 0:
                row = {
                    "mode": mode,
                    "repetition": repetition + 1,
                    "height": args.height,
                    "width": args.width,
                    "window_size": 5,
                    "d_min": 0,
                    "d_max": 8,
                    "wall_seconds": wall_seconds,
                }
                for key in METRIC_KEYS:
                    row[key] = stats.get(key, "")
                rows.append(row)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        mode: median(row["wall_seconds"] for row in rows if row["mode"] == mode)
        for mode in modes
    }
    baseline = summary["sequential"]
    print("\nRESULTADOS PRELIMINARES")
    print(f"Resolucion: {args.height} x {args.width}")
    print("-------------------------------")
    for mode in modes:
        elapsed = summary[mode]
        print(f"{mode:14s} | {elapsed:.4f} s | Speedup: {baseline / elapsed:.3f}x")
    print(f"\nCSV generado: {output}")
    print("Equivalencia SAD verificada en todas las ejecuciones.")
    print("Nota: send_call_seconds y connect_call_seconds NO son latencia pura de red.")


if __name__ == "__main__":
    main()
