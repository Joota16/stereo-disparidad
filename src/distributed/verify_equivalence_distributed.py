"""Verificacion formal de equivalencia numerica entre SAD distribuido y secuencial (T17)."""

import argparse
import socket
import threading
import time
from pathlib import Path

import numpy as np

from src.common.io_utils import load_stereo_pair
from src.distributed.master import run_master
from src.distributed.worker import run_worker
from src.stereo.sad import compute_sad


def _start_local_worker(endpoint: str, num_requests: int = 1):
    ready_event = threading.Event()
    worker_thread = threading.Thread(
        target=run_worker,
        args=({"bind": endpoint, "max_requests": num_requests, "ready_event": ready_event},),
        daemon=True,
    )
    worker_thread.start()
    if not ready_event.wait(timeout=5.0):
        raise RuntimeError("No se pudo inicializar el trabajador local para la prueba.")
    return worker_thread


def verify_equivalence_on_pair(
    left_img: np.ndarray,
    right_img: np.ndarray,
    window_size: int,
    d_min: int,
    d_max: int,
    endpoint: str,
    case_name: str,
):
    print(f"\n--- Evaluando caso: {case_name} (K={window_size}, D=[{d_min}, {d_max}]) ---")

    # 1. Calculo secuencial de referencia
    t0_seq = time.perf_counter()
    disp_seq, mask_seq = compute_sad(left_img, right_img, window_size, d_min, d_max)
    t_seq = time.perf_counter() - t0_seq

    # 2. Calculo distribuido (Maestro + Trabajador ZeroMQ)
    t0_dist = time.perf_counter()
    disp_dist, mask_dist, stats = run_master({
        "left_gray": left_img,
        "right_gray": right_img,
        "window_size": window_size,
        "d_min": d_min,
        "d_max": d_max,
        "connect": endpoint,
        "timeout_ms": 30000,
    })
    t_dist = time.perf_counter() - t0_dist

    # 3. Validacion estricta de igualdad de mascaras
    mask_equal = np.array_equal(mask_dist, mask_seq)
    if not mask_equal:
        mismatch_count = np.sum(mask_dist != mask_seq)
        raise AssertionError(f"[{case_name}] Discrepancia en mascaras de validez: {mismatch_count} pixeles difieren.")

    # 4. Validacion estricta de valores de disparidad en pixeles validos
    valid_coords = mask_seq
    valid_pixels = np.sum(valid_coords)
    diff_abs = np.abs(disp_dist[valid_coords] - disp_seq[valid_coords])
    max_diff = float(np.max(diff_abs)) if valid_pixels > 0 else 0.0

    if max_diff > 0.0:
        raise AssertionError(f"[{case_name}] Discrepancia en mapa de disparidad: dif maxima = {max_diff:.6f} px.")

    print(f"  Pixeles evaluados: {left_img.size} (validos: {valid_pixels})")
    print(f"  Coincidencia de mascara: 100.0% exacta")
    print(f"  Diferencia absoluta maxima en disparidad: {max_diff:.6f} px")
    print(f"  Tiempo secuencial: {t_seq:.4f} s | Tiempo distribuido total: {t_dist:.4f} s")
    print(f"  Bytes transferidos (req/resp): {stats['request_payload_bytes']} / {stats['response_payload_bytes']}")
    print(f"  Resultado: [APROBADO] Equivalencia estricta verificada.")

    return {
        "case": case_name,
        "window_size": window_size,
        "d_min": d_min,
        "d_max": d_max,
        "valid_pixels": int(valid_pixels),
        "max_diff": max_diff,
        "mask_equal": mask_equal,
        "t_seq": t_seq,
        "t_dist": t_dist,
    }


def main():
    parser = argparse.ArgumentParser(description="Verificacion de equivalencia distribuida vs secuencial (T17)")
    parser.add_argument("--connect", default=None, help="Endpoint del trabajador remoto (ej. tcp://192.168.1.50:5555). Si se omite, se usa trabajador local.")
    args = parser.parse_args()

    remote_mode = args.connect is not None
    endpoint = args.connect
    worker_thread = None

    # Configuraciones de prueba
    configs = [
        {"window_size": 5, "d_min": 0, "d_max": 16, "name": "Adirondack_Q (K=5, D=16)"},
        {"window_size": 9, "d_min": 0, "d_max": 16, "name": "Adirondack_Q (K=9, D=16)"},
        {"window_size": 5, "d_min": 0, "d_max": 32, "name": "Adirondack_Q (K=5, D=32)"},
    ]

    total_runs = len(configs)

    if not remote_mode:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        endpoint = f"tcp://127.0.0.1:{port}"
        print(f"[INFO] Modo autonomo: levantando trabajador local en {endpoint} para {total_runs} solicitudes...")
        worker_thread = _start_local_worker(endpoint, num_requests=total_runs)
    else:
        print(f"[INFO] Modo remoto: conectando a trabajador en {endpoint}...")

    # Cargar imagen real de Middlebury Adirondack (Quarter)
    data_dir = Path("data/raw/adirondack_Q")
    left_path = data_dir / "im0.png"
    right_path = data_dir / "im1.png"

    if left_path.exists() and right_path.exists():
        left_img, right_img = load_stereo_pair(str(left_path), str(right_path))
    else:
        print("[WARN] Imagenes de Adirondack no encontradas. Generando matriz sintetica con textura.")
        rng = np.random.default_rng(2026)
        left_img = rng.integers(0, 256, size=(120, 180), dtype=np.uint8)
        right_img = np.roll(left_img, -6, axis=1)

    print("======================================================================")
    print(" VERIFICACION DE EQUIVALENCIA DISTRIBUIDA (T17) - LÍNEA BASE VS ZEROMQ")
    print("======================================================================")

    results = []
    for cfg in configs:
        res = verify_equivalence_on_pair(
            left_img,
            right_img,
            cfg["window_size"],
            cfg["d_min"],
            cfg["d_max"],
            endpoint,
            cfg["name"],
        )
        results.append(res)

    if worker_thread is not None:
        worker_thread.join(timeout=5.0)

    print("\n======================================================================")
    print(" RESUMEN FINAL DE EQUIVALENCIA (T17)")
    print("======================================================================")
    print(f"{'Configuracion':<30} | {'Mascara':<10} | {'Dif Max (px)':<14} | {'Estado':<10}")
    print("-" * 72)
    for r in results:
        mask_str = "Identica" if r["mask_equal"] else "FALLO"
        diff_str = f"{r['max_diff']:.6f}"
        status_str = "OK" if r["mask_equal"] and r["max_diff"] == 0.0 else "FALLO"
        print(f"{r['case']:<30} | {mask_str:<10} | {diff_str:<14} | {status_str:<10}")
    print("======================================================================")
    print("Conclusion: La version distribuida en dos nodos preserva la exactitud")
    print("numerica del 100% de la linea base secuencial (cero distorsion).")


if __name__ == "__main__":
    main()
