"""Automatizacion y ejecucion reproducible del benchmark de disparidad estereo (T19)."""

import argparse
import csv
import socket
import threading
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from src.common.io_utils import load_stereo_pair
from src.distributed.master import run_master
from src.distributed.worker import run_worker
from src.parallel.multiprocess import compute_disparity_parallel
from src.stereo.sad import compute_sad


def _start_loopback_worker(endpoint: str):
    ready_evt = threading.Event()
    worker_th = threading.Thread(
        target=run_worker,
        args=({"bind": endpoint, "max_requests": None, "ready_event": ready_evt},),
        daemon=True,
    )
    worker_th.start()
    if not ready_evt.wait(timeout=5.0):
        raise RuntimeError("No se pudo iniciar el trabajador de loopback.")
    return worker_th


def execute_mode(
    mode: str,
    left: np.ndarray,
    right: np.ndarray,
    window_size: int,
    d_min: int,
    d_max: int,
    endpoint: str = None,
) -> Tuple[np.ndarray, np.ndarray, float]:
    t0 = time.perf_counter()
    if mode == "secuencial":
        disp, mask = compute_sad(left, right, window_size, d_min, d_max)
    elif mode == "multiproceso_p2":
        disp, mask = compute_disparity_parallel(left, right, window_size, d_min, d_max, workers=2)
    elif mode == "multiproceso_p4":
        disp, mask = compute_disparity_parallel(left, right, window_size, d_min, d_max, workers=4)
    elif mode == "distribuido_zmq":
        disp, mask, stats = run_master({
            "left_gray": left,
            "right_gray": right,
            "window_size": window_size,
            "d_min": d_min,
            "d_max": d_max,
            "connect": endpoint,
            "timeout_ms": 60000,
        })
    else:
        raise ValueError(f"Modalidad no reconocida: {mode}")
    elapsed = time.perf_counter() - t0
    return disp, mask, elapsed


def run_benchmark_cell(
    case_name: str,
    left: np.ndarray,
    right: np.ndarray,
    window_size: int,
    d_min: int,
    d_max: int,
    modes: List[str],
    reps: int,
    warmup: int,
    endpoint: str,
) -> List[Dict]:
    results = []
    baseline_median = None

    print(f"\n======================================================================")
    print(f" BENCHMARK: {case_name} (H={left.shape[0]}, W={left.shape[1]}, K={window_size}, D=[{d_min}, {d_max}])")
    print(f" Configuracion: {warmup} calentamiento(s), {reps} repeticiones medidas")
    print(f"======================================================================")

    for mode in modes:
        # 1. Warm-up (descartado de estadisticas)
        for w in range(warmup):
            print(f"  [{mode}] Calentamiento {w + 1}/{warmup}...", flush=True)
            execute_mode(mode, left, right, window_size, d_min, d_max, endpoint)

        # 2. Mediciones formales
        times = []
        for r in range(reps):
            disp, mask, elapsed = execute_mode(mode, left, right, window_size, d_min, d_max, endpoint)
            times.append(elapsed)
            print(f"  [{mode}] Repeticion {r + 1}/{reps}: {elapsed:.4f} s", flush=True)

        t_mean = float(np.mean(times))
        t_std = float(np.std(times))
        t_median = float(np.median(times))
        t_min = float(np.min(times))
        t_max = float(np.max(times))

        if mode == "secuencial":
            baseline_median = t_median

        # Speedup y Eficiencia
        p_factor = 1 if mode == "secuencial" else (2 if mode in ("multiproceso_p2", "distribuido_zmq") else 4)
        speedup = (baseline_median / t_median) if baseline_median is not None and t_median > 0 else 1.0
        efficiency = speedup / p_factor

        row = {
            "caso": case_name,
            "alto": left.shape[0],
            "ancho": left.shape[1],
            "ventana": window_size,
            "d_min": d_min,
            "d_max": d_max,
            "modalidad": mode,
            "procesos": p_factor,
            "repeticiones": reps,
            "media_s": round(t_mean, 4),
            "desv_std_s": round(t_std, 4),
            "mediana_s": round(t_median, 4),
            "min_s": round(t_min, 4),
            "max_s": round(t_max, 4),
            "speedup": round(speedup, 3),
            "eficiencia": round(efficiency, 3),
        }
        results.append(row)

    return results


def main():
    parser = argparse.ArgumentParser(description="Automatizacion de Benchmark Grid de SAD (T19)")
    parser.add_argument("--reps", type=int, default=3, help="Numero de repeticiones medidas")
    parser.add_argument("--warmup", type=int, default=1, help="Numero de corridas de calentamiento")
    parser.add_argument("--output", default="results/t19_benchmark_grid.csv", help="Ruta del archivo CSV")
    parser.add_argument("--connect", default=None, help="Endpoint remoto (ej. tcp://IP:5555). Si se omite, usa loopback.")
    parser.add_argument("--quick", action="store_true", help="Modo rapido con resolucion reducida para pruebas agiles")
    args = parser.parse_args()

    out_csv = Path(args.output)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    # Cargar imagenes
    if args.quick:
        rng = np.random.default_rng(2026)
        left = rng.integers(0, 256, size=(120, 180), dtype=np.uint8)
        right = np.roll(left, -4, axis=1)
        grid = [
            {"name": "Sintetica_120x180 (K=5, D=16)", "K": 5, "d_min": 0, "d_max": 16, "left": left, "right": right},
        ]
    else:
        left_path = Path("data/raw/adirondack_Q/im0.png")
        right_path = Path("data/raw/adirondack_Q/im1.png")
        if not left_path.exists():
            raise FileNotFoundError(f"No se encontro {left_path}")
        left, right = load_stereo_pair(str(left_path), str(right_path))

        grid = [
            {"name": "Adirondack_Q (K=5, D=16)", "K": 5, "d_min": 0, "d_max": 16, "left": left, "right": right},
            {"name": "Adirondack_Q (K=9, D=16)", "K": 9, "d_min": 0, "d_max": 16, "left": left, "right": right},
            {"name": "Adirondack_Q (K=5, D=32)", "K": 5, "d_min": 0, "d_max": 32, "left": left, "right": right},
        ]

    modes = ["secuencial", "multiproceso_p2", "multiproceso_p4", "distribuido_zmq"]

    # Iniciar trabajador de loopback si no se proveyo endpoint remoto
    worker_th = None
    endpoint = args.connect
    if endpoint is None:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        endpoint = f"tcp://127.0.0.1:{port}"
        print(f"[INFO] Iniciando trabajador local de loopback continuo en {endpoint}...")
        worker_th = _start_loopback_worker(endpoint)

    all_rows = []
    try:
        for item in grid:
            rows = run_benchmark_cell(
                item["name"],
                item["left"],
                item["right"],
                item["K"],
                item["d_min"],
                item["d_max"],
                modes,
                args.reps,
                args.warmup,
                endpoint,
            )
            all_rows.extend(rows)
    finally:
        if worker_th is not None:
            worker_th.join(timeout=3.0)

    # Guardar en CSV
    fieldnames = [
        "caso", "alto", "ancho", "ventana", "d_min", "d_max",
        "modalidad", "procesos", "repeticiones", "media_s",
        "desv_std_s", "mediana_s", "min_s", "max_s", "speedup", "eficiencia"
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n======================================================================")
    print(f" RESUMEN FINAL DEL BENCHMARK (Guardado en {out_csv})")
    print(f"======================================================================")
    print(f"{'Caso':<28} | {'Modalidad':<16} | {'Mediana (s)':<11} | {'Speedup':<8} | {'Eficiencia':<10}")
    print("-" * 82)
    for r in all_rows:
        print(f"{r['caso']:<28} | {r['modalidad']:<16} | {r['mediana_s']:<11.4f} | {r['speedup']:<8.3f} | {r['eficiencia']:<10.3f}")
    print("======================================================================")


if __name__ == "__main__":
    main()
