"""Ejecutor de benchmarks de disparidad estereo."""

import argparse
import csv
import json
import platform
import random
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import zmq

from src.common.io_utils import load_stereo_pair
from src.distributed.master import run_master
from src.distributed.worker import run_worker
from src.parallel.multiprocess import compute_disparity_parallel
from src.stereo.sad import compute_sad


def get_environment_metadata() -> Dict[str, Any]:
    """Obtiene metadatos del entorno para garantizar trazabilidad cientifica."""
    git_commit = "desconocido"
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        pass

    return {
        "timestamp": datetime.now().isoformat(),
        "git_commit": git_commit,
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "cv2_version": cv2.__version__,
        "zmq_version": zmq.__version__,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "hostname": platform.node(),
    }


def _start_loopback_worker(endpoint: str) -> threading.Thread:
    ready_evt = threading.Event()
    worker_th = threading.Thread(
        target=run_worker,
        args=({"bind": endpoint, "max_requests": None, "ready_event": ready_evt},),
        daemon=True,
    )
    worker_th.start()
    if not ready_evt.wait(timeout=5.0):
        raise RuntimeError("No se pudo iniciar el trabajador local de loopback.")
    return worker_th


def execute_mode(
    mode: str,
    left: np.ndarray,
    right: np.ndarray,
    window_size: int,
    d_min: int,
    d_max: int,
    endpoint: Optional[str] = None,
) -> Tuple[np.ndarray, np.ndarray, float, Optional[Dict[str, Any]]]:
    """
    Ejecuta una modalidad cronometrando estrictamente la llamada de calculo.
    Retorna (disparidad, mascara, tiempo_segundos, estadisticas_opcionales).
    """
    t0 = time.perf_counter()
    stats = None

    if mode == "secuencial":
        disp, mask = compute_sad(left, right, window_size, d_min, d_max)
    elif mode == "multiproceso_p2":
        disp, mask = compute_disparity_parallel(left, right, window_size, d_min, d_max, workers=2)
    elif mode == "multiproceso_p4":
        disp, mask = compute_disparity_parallel(left, right, window_size, d_min, d_max, workers=4)
    elif mode.startswith("distribuido"):
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
    return disp, mask, elapsed, stats


def append_csv_row(csv_path: Path, fieldnames: List[str], row: Dict[str, Any]):
    """Escribe progresivamente una fila en el CSV para evitar perdida de datos ante fallos."""
    write_header = not csv_path.exists()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def run_benchmark_grid(
    grid_configs: List[Dict[str, Any]],
    modes: List[str],
    reps: int = 5,
    warmup: int = 1,
    endpoint: Optional[str] = None,
    output_runs_csv: str = "results/t19_benchmark_runs.csv",
    output_summary_csv: str = "results/t19_benchmark_summary.csv",
    counterbalance: bool = False,
    overwrite: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Ejecuta la matriz de pruebas parametrizada, validando equivalencia por repeticion
    y guardando resultados de corridas individuales y resumen agregado.
    """
    if reps < 1:
        raise ValueError(f"El numero de repeticiones debe ser >= 1 (recibido: {reps})")
    if warmup < 0:
        raise ValueError(f"El numero de calentamientos debe ser >= 0 (recibido: {warmup})")
    if "secuencial" not in modes:
        raise ValueError("Se requiere la modalidad secuencial como referencia de speedup")
    if len(set(modes)) != len(modes):
        raise ValueError("No deben repetirse modalidades en un mismo benchmark")

    runs_csv_p = Path(output_runs_csv)
    summary_csv_p = Path(output_summary_csv)
    runs_csv_p.parent.mkdir(parents=True, exist_ok=True)
    summary_csv_p.parent.mkdir(parents=True, exist_ok=True)
    if runs_csv_p.resolve() == summary_csv_p.resolve():
        raise ValueError("Los CSV de repeticiones y resumen deben tener rutas diferentes")
    meta_path = runs_csv_p.with_name(f"{runs_csv_p.stem}_metadata.json")
    if not overwrite and any(p.exists() for p in (runs_csv_p, summary_csv_p, meta_path)):
        raise FileExistsError("Ya existen resultados: usa otras rutas o --overwrite explicitamente")
    if overwrite:
        for path in (runs_csv_p, summary_csv_p):
            if path.exists():
                path.unlink()

    is_loopback = (endpoint is None) or ("127.0.0.1" in endpoint) or ("localhost" in endpoint)
    dist_mode_name = "distribuido_loopback" if is_loopback else "distribuido_lan"
    resolved_modes = [dist_mode_name if m == "distribuido" else m for m in modes]

    # Iniciar trabajador loopback si es necesario
    worker_th = None
    if any(m.startswith("distribuido") for m in resolved_modes) and is_loopback:
        if endpoint is None:
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            endpoint = f"tcp://127.0.0.1:{port}"
        print(f"[INFO] Trabajador ZeroMQ loopback iniciado en {endpoint}")
        worker_th = _start_loopback_worker(endpoint)

    runs_fields = [
        "run_id", "timestamp", "caso", "alto", "ancho", "ventana_K", "d_min", "d_max",
        "modalidad", "tipo_conexion", "endpoint", "procesos", "repeticion_num",
        "es_calentamiento", "tiempo_s", "equivalente",
        "partition_s", "serialize_s", "socket_setup_s", "send_call_s",
        "local_compute_s", "receive_wait_s", "remote_compute_s", "response_decode_s",
        "merge_s", "request_bytes", "response_bytes"
    ]

    summary_fields = [
        "caso", "alto", "ancho", "ventana_K", "d_min", "d_max", "modalidad",
        "tipo_conexion", "procesos", "repeticiones", "media_s", "mediana_s",
        "desv_std_s", "min_s", "max_s", "speedup", "eficiencia_local", "nota_metodologica"
    ]

    env_meta = get_environment_metadata()
    env_meta["experiment"] = {
        "modes": resolved_modes, "repetitions": reps, "warmup": warmup,
        "endpoint": endpoint or "loopback local",
        "cases": [{"name": c["name"], "K": c["K"], "d_min": c["d_min"],
                   "d_max": c["d_max"], "shape": list(c["left"].shape)}
                  for c in grid_configs],
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(env_meta, f, indent=2)

    all_runs: List[Dict[str, Any]] = []
    all_summaries: List[Dict[str, Any]] = []
    run_counter = 0

    try:
        for cell in grid_configs:
            case_name = cell["name"]
            left = cell["left"]
            right = cell["right"]
            K = cell["K"]
            d_min = cell["d_min"]
            d_max = cell["d_max"]
            h, w = left.shape

            print(f"\n{'='*75}")
            print(f" BENCHMARK CELDA: {case_name} | {h}x{w} | K={K} | D=[{d_min}, {d_max}]")
            print(f"{'='*75}")

            # 1. Obtener referencia secuencial absoluta para validacion
            print(f"  [referencia] Generando linea base secuencial...")
            ref_disp, ref_mask, _, _ = execute_mode("secuencial", left, right, K, d_min, d_max)

            cell_modes = list(resolved_modes)
            if counterbalance:
                random.shuffle(cell_modes)

            mode_times: Dict[str, List[float]] = {m: [] for m in cell_modes}

            for mode in cell_modes:
                # Determinar numero de procesos
                if mode == "secuencial":
                    n_procs = 1
                elif mode in ("multiproceso_p2", "distribuido_loopback", "distribuido_lan"):
                    n_procs = 2
                elif mode == "multiproceso_p4":
                    n_procs = 4
                else:
                    n_procs = 1

                # Calentamiento
                for warm_i in range(warmup):
                    run_counter += 1
                    disp_w, mask_w, t_w, stats_w = execute_mode(mode, left, right, K, d_min, d_max, endpoint)
                    # Validar equivalencia fuera del cronometro
                    equiv = bool(np.array_equal(mask_w, ref_mask) and np.allclose(disp_w, ref_disp, atol=0.0, rtol=0.0, equal_nan=True))
                    if not equiv:
                        raise AssertionError(f"Fallo equivalencia en calentamiento: {case_name}, {mode}")
                    run_record = {
                        "run_id": run_counter, "timestamp": datetime.now().isoformat(),
                        "caso": case_name, "alto": h, "ancho": w, "ventana_K": K,
                        "d_min": d_min, "d_max": d_max, "modalidad": mode,
                        "tipo_conexion": (("loopback" if is_loopback else "lan_remota")
                                   if mode.startswith("distribuido") else "local"),
                        "endpoint": endpoint or "n/a", "procesos": n_procs,
                        "repeticion_num": warm_i + 1, "es_calentamiento": True,
                        "tiempo_s": round(t_w, 6), "equivalente": equiv,
                        "partition_s": round(stats_w.get("partition_seconds", 0.0), 6) if stats_w else "",
                        "serialize_s": round(stats_w.get("serialize_seconds", 0.0), 6) if stats_w else "",
                        "socket_setup_s": round(stats_w.get("socket_setup_seconds", 0.0), 6) if stats_w else "",
                        "send_call_s": round(stats_w.get("send_call_seconds", 0.0), 6) if stats_w else "",
                        "local_compute_s": round(stats_w.get("local_compute_seconds", 0.0), 6) if stats_w else "",
                        "receive_wait_s": round(stats_w.get("receive_wait_seconds", 0.0), 6) if stats_w else "",
                        "remote_compute_s": round(stats_w.get("remote_compute_seconds", 0.0), 6) if stats_w else "",
                        "response_decode_s": round(stats_w.get("response_decode_seconds", 0.0), 6) if stats_w else "",
                        "merge_s": round(stats_w.get("merge_seconds", 0.0), 6) if stats_w else "",
                        "request_bytes": stats_w.get("request_payload_bytes", "") if stats_w else "",
                        "response_bytes": stats_w.get("response_payload_bytes", "") if stats_w else "",
                    }
                    all_runs.append(run_record)
                    append_csv_row(runs_csv_p, runs_fields, run_record)

                # Mediciones formales
                for rep_i in range(reps):
                    run_counter += 1
                    disp, mask, t_calc, stats = execute_mode(mode, left, right, K, d_min, d_max, endpoint)
                    # Validacion de equivalencia estricta fuera del cronometro
                    equiv = bool(np.array_equal(mask, ref_mask) and np.allclose(disp, ref_disp, atol=0.0, rtol=0.0, equal_nan=True))
                    if not equiv:
                        raise AssertionError(
                            f"Fallo equivalencia: {case_name}, {mode}, repeticion {rep_i+1}"
                        )

                    mode_times[mode].append(t_calc)

                    run_record = {
                        "run_id": run_counter, "timestamp": datetime.now().isoformat(),
                        "caso": case_name, "alto": h, "ancho": w, "ventana_K": K,
                        "d_min": d_min, "d_max": d_max, "modalidad": mode,
                        "tipo_conexion": (("loopback" if is_loopback else "lan_remota")
                                   if mode.startswith("distribuido") else "local"),
                        "endpoint": endpoint or "n/a", "procesos": n_procs,
                        "repeticion_num": rep_i + 1, "es_calentamiento": False,
                        "tiempo_s": round(t_calc, 6), "equivalente": equiv,
                        "partition_s": round(stats.get("partition_seconds", 0.0), 6) if stats else "",
                        "serialize_s": round(stats.get("serialize_seconds", 0.0), 6) if stats else "",
                        "socket_setup_s": round(stats.get("socket_setup_seconds", 0.0), 6) if stats else "",
                        "send_call_s": round(stats.get("send_call_seconds", 0.0), 6) if stats else "",
                        "local_compute_s": round(stats.get("local_compute_seconds", 0.0), 6) if stats else "",
                        "receive_wait_s": round(stats.get("receive_wait_seconds", 0.0), 6) if stats else "",
                        "remote_compute_s": round(stats.get("remote_compute_seconds", 0.0), 6) if stats else "",
                        "response_decode_s": round(stats.get("response_decode_seconds", 0.0), 6) if stats else "",
                        "merge_s": round(stats.get("merge_seconds", 0.0), 6) if stats else "",
                        "request_bytes": stats.get("request_payload_bytes", "") if stats else "",
                        "response_bytes": stats.get("response_payload_bytes", "") if stats else "",
                    }
                    all_runs.append(run_record)
                    append_csv_row(runs_csv_p, runs_fields, run_record)
                    print(f"  [{mode}] Rep {rep_i+1}/{reps}: {t_calc:.4f} s | Eq: {equiv}", flush=True)

            # 2. Resumen de la celda
            seq_median = float(np.median(mode_times["secuencial"]))
            for mode in cell_modes:
                t_arr = mode_times[mode]
                t_mean = float(np.mean(t_arr))
                t_median = float(np.median(t_arr))
                t_std = float(np.std(t_arr))
                t_min = float(np.min(t_arr))
                t_max = float(np.max(t_arr))

                speedup = round(seq_median / t_median, 3) if t_median > 0 else 1.0

                # Eficiencia solo es metodologicamente valida para CPU local homogeneo
                if mode.startswith("distribuido"):
                    efficiency = "N/A"
                    note = ("Control ZeroMQ loopback; no representa dos nodos fisicos."
                            if mode == "distribuido_loopback"
                            else "Cluster heterogeneo PC+Laptop; eficiencia homogenea no aplicable.")
                    n_procs = 2
                elif mode == "secuencial":
                    efficiency = 1.000
                    note = "Linea base de referencia (Ts)."
                    n_procs = 1
                else:
                    n_procs = 2 if mode == "multiproceso_p2" else 4
                    efficiency = round(speedup / n_procs, 3)
                    note = f"Paralelismo homogeneo local con {n_procs} procesos."

                summary_row = {
                    "caso": case_name, "alto": h, "ancho": w, "ventana_K": K,
                    "d_min": d_min, "d_max": d_max, "modalidad": mode,
                    "tipo_conexion": (("loopback" if is_loopback else "lan_remota")
                                   if mode.startswith("distribuido") else "local"),
                    "procesos": n_procs, "repeticiones": reps,
                    "media_s": round(t_mean, 4), "mediana_s": round(t_median, 4),
                    "desv_std_s": round(t_std, 4), "min_s": round(t_min, 4),
                    "max_s": round(t_max, 4), "speedup": speedup,
                    "eficiencia_local": efficiency, "nota_metodologica": note,
                }
                all_summaries.append(summary_row)
                append_csv_row(summary_csv_p, summary_fields, summary_row)

    finally:
        pass

    return all_runs, all_summaries


def build_default_grid(mode: str) -> List[Dict[str, Any]]:
    """Construye la matriz experimental segun el alcance: quick, pilot o formal."""
    if mode == "quick":
        rng = np.random.default_rng(2026)
        l = rng.integers(0, 256, size=(120, 180), dtype=np.uint8)
        r = np.roll(l, -4, axis=1)
        return [{"name": "Sintetica_120x180 (K=5, D=16)", "K": 5, "d_min": 0, "d_max": 16, "left": l, "right": r}]

    data_dir = Path("data/raw/Adirondack_Q")
    if not (data_dir / "im0.png").exists():
        raise FileNotFoundError(f"No se encontro {data_dir / 'im0.png'}")
    left, right = load_stereo_pair(str(data_dir / "im0.png"), str(data_dir / "im1.png"))

    if mode == "pilot":
        return [
            {"name": "Adirondack_Q (K=5, D=16)", "K": 5, "d_min": 0, "d_max": 16, "left": left, "right": right},
            {"name": "Adirondack_Q (K=9, D=16)", "K": 9, "d_min": 0, "d_max": 16, "left": left, "right": right},
            {"name": "Adirondack_Q (K=5, D=32)", "K": 5, "d_min": 0, "d_max": 32, "left": left, "right": right},
        ]
    elif mode == "formal":
        return [
            {"name": "Adirondack_Q (K=5, D=16)", "K": 5, "d_min": 0, "d_max": 16, "left": left, "right": right},
            {"name": "Adirondack_Q (K=7, D=16)", "K": 7, "d_min": 0, "d_max": 16, "left": left, "right": right},
            {"name": "Adirondack_Q (K=9, D=16)", "K": 9, "d_min": 0, "d_max": 16, "left": left, "right": right},
            {"name": "Adirondack_Q (K=5, D=32)", "K": 5, "d_min": 0, "d_max": 32, "left": left, "right": right},
            {"name": "Adirondack_Q (K=7, D=32)", "K": 7, "d_min": 0, "d_max": 32, "left": left, "right": right},
            {"name": "Adirondack_Q (K=9, D=32)", "K": 9, "d_min": 0, "d_max": 32, "left": left, "right": right},
        ]
    else:
        raise ValueError(f"Modo de rejilla desconocido: {mode}")


def main():
    parser = argparse.ArgumentParser(description="Ejecutor de benchmark parametrizado")
    parser.add_argument("--scope", choices=["quick", "pilot", "formal"], default="pilot", help="Alcance de la rejilla")
    parser.add_argument("--reps", type=int, default=3, help="Repeticiones medidas (formal=10)")
    parser.add_argument("--warmup", type=int, default=1, help="Corridas de calentamiento descartadas")
    parser.add_argument("--connect", default=None, help="Endpoint remoto (ej. tcp://IP:5555). Omita para loopback local.")
    parser.add_argument("--output-runs", default="results/t19_benchmark_runs.csv", help="CSV de ejecuciones individuales")
    parser.add_argument("--output-summary", default="results/t19_benchmark_summary.csv", help="CSV resumen estadistico")
    parser.add_argument("--counterbalance", action="store_true", help="Aleatorizar el orden de bloques por configuracion")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescribir archivos de salida existentes")
    args = parser.parse_args()

    grid = build_default_grid(args.scope)
    modes = ["secuencial", "multiproceso_p2", "multiproceso_p4", "distribuido"]

    print(f"\nIniciando Benchmark Grid ({args.scope}) con {len(grid)} celda(s) y {args.reps} repeticion(es)...")
    runs, summary = run_benchmark_grid(
        grid_configs=grid,
        modes=modes,
        reps=args.reps,
        warmup=args.warmup,
        endpoint=args.connect,
        output_runs_csv=args.output_runs,
        output_summary_csv=args.output_summary,
        counterbalance=args.counterbalance,
        overwrite=args.overwrite,
    )

    print(f"\n=========================================================================================")
    print(f" RESUMEN FINAL DEL BENCHMARK (Guardado en {args.output_summary})")
    print(f"=========================================================================================")
    print(f"{'Caso':<28} | {'Modalidad':<22} | {'Mediana (s)':<11} | {'Speedup':<8} | {'Eficiencia':<11}")
    print("-" * 92)
    for s in summary:
        eff_str = f"{s['eficiencia_local']:.3f}" if isinstance(s['eficiencia_local'], (int, float)) else str(s['eficiencia_local'])
        print(f"{s['caso']:<28} | {s['modalidad']:<22} | {s['mediana_s']:<11.4f} | {s['speedup']:<8.3f} | {eff_str:<11}")
    print(f"=========================================================================================")


if __name__ == "__main__":
    main()
