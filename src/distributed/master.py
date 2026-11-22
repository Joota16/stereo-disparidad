"""T18: maestro SAD distribuido con métricas de fases del lado maestro.

Las medidas de enviar/conectar son duración de llamadas ZeroMQ,
NO tiempo puro de transporte de red. Se conserva el contrato T15.
"""

import argparse
from uuid import uuid4
from time import perf_counter

import numpy as np
import zmq

from src.parallel.partition import split_rows, merge_rows
from src.stereo.sad import compute_sad
from src.distributed.protocol import encode_request, decode_response


def run_master(config):
    overall_start = perf_counter()
    left = config["left_gray"]
    right = config["right_gray"]
    window = config.get("window_size", 5)
    d_min = config.get("d_min", 0)
    d_max = config.get("d_max", 8)
    endpoint = config.get("connect", "tcp://127.0.0.1:5555")
    timeout = config.get("timeout_ms", 30000)

    if (not isinstance(left, np.ndarray) or not isinstance(right, np.ndarray)
            or left.ndim != 2 or left.shape != right.shape
            or left.dtype != np.uint8 or right.dtype != np.uint8):
        raise ValueError("Ambas imagenes deben ser matrices 2D uint8 de igual forma")

    h, w = left.shape
    t0 = perf_counter()
    parts = split_rows(h, 2, window)
    local, remote = parts
    partition_seconds = perf_counter() - t0

    job_id = uuid4().hex
    t0 = perf_counter()
    request = encode_request(
        remote,
        left[remote["halo_start"]:remote["halo_end"]],
        right[remote["halo_start"]:remote["halo_end"]],
        h, window, d_min, d_max, job_id,
    )
    serialize_seconds = perf_counter() - t0

    t0 = perf_counter()
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.SNDTIMEO, timeout)
    socket.setsockopt(zmq.RCVTIMEO, timeout)
    socket_setup_seconds = perf_counter() - t0

    try:
        t0 = perf_counter()
        socket.connect(endpoint)
        connect_call_seconds = perf_counter() - t0

        t0 = perf_counter()
        socket.send_multipart(request)
        send_call_seconds = perf_counter() - t0

        t0 = perf_counter()
        hs, he = local["halo_start"], local["halo_end"]
        local_disp, local_mask = compute_sad(
            left[hs:he], right[hs:he], window, d_min, d_max
        )
        local_seconds = perf_counter() - t0

        t0 = perf_counter()
        response = socket.recv_multipart()
        receive_wait_seconds = perf_counter() - t0

        t0 = perf_counter()
        remote_disp, remote_mask, remote_seconds = decode_response(
            response, job_id, remote, w
        )
        response_decode_seconds = perf_counter() - t0

        t0 = perf_counter()
        full_disp, full_mask = merge_rows([
            {**local, "disparity_map": local_disp, "valid_mask": local_mask},
            {**remote, "disparity_map": remote_disp, "valid_mask": remote_mask},
        ], h, w)
        merge_seconds = perf_counter() - t0

        total_seconds = perf_counter() - overall_start
        stats = {
            # Métricas del contrato anterior T15 (se mantienen)
            "total_seconds": total_seconds,
            "local_compute_seconds": local_seconds,
            "remote_compute_seconds": remote_seconds,
            "receive_wait_seconds": receive_wait_seconds,
            "request_payload_bytes": sum(map(len, request)),
            "response_payload_bytes": sum(map(len, response)),
            # Nuevas métricas del lado maestro T18
            "partition_seconds": partition_seconds,
            "serialize_seconds": serialize_seconds,
            "socket_setup_seconds": socket_setup_seconds,
            "connect_call_seconds": connect_call_seconds,
            "send_call_seconds": send_call_seconds,
            "response_decode_seconds": response_decode_seconds,
            "merge_seconds": merge_seconds,
        }
        return full_disp, full_mask, stats
    except zmq.Again as exc:
        raise TimeoutError("No se recibio respuesta ZeroMQ; revisar worker y firewall") from exc
    finally:
        socket.close()
        context.term()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--connect", default="tcp://127.0.0.1:5555")
    parser.add_argument("--height", type=int, default=48)
    parser.add_argument("--width", type=int, default=72)
    args = parser.parse_args()

    rng = np.random.default_rng(2026)
    left = rng.integers(0, 256, size=(args.height, args.width), dtype=np.uint8)
    right = rng.integers(0, 256, size=(args.height, args.width), dtype=np.uint8)
    disp, mask, stats = run_master({
        "left_gray": left, "right_gray": right,
        "connect": args.connect, "window_size": 5, "d_min": 0, "d_max": 8,
    })
    baseline_disp, baseline_mask = compute_sad(left, right, 5, 0, 8)
    np.testing.assert_array_equal(mask, baseline_mask)
    np.testing.assert_allclose(disp, baseline_disp, atol=0, rtol=0, equal_nan=True)
    print("T18 OK: SAD distribuido = SAD secuencial (mapa y mascara)")
    for key, value in stats.items():
        print(f"  {key}: {value:.6f}" if key.endswith("seconds") else f"  {key}: {value}")


if __name__ == "__main__":
    main()
