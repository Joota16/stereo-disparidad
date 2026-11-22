"""T15: maestro: calcula SAD local y remoto en paralelo y ensambla."""

import argparse
from uuid import uuid4
from time import perf_counter

import numpy as np
import zmq

from src.parallel.partition import split_rows, merge_rows
from src.stereo.sad import compute_sad
from src.distributed.protocol import encode_request, decode_response


def run_master(config):
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
    parts = split_rows(h, 2, window)
    local, remote = parts
    job_id = uuid4().hex
    request = encode_request(
        remote,
        left[remote["halo_start"]:remote["halo_end"]],
        right[remote["halo_start"]:remote["halo_end"]],
        h, window, d_min, d_max, job_id,
    )

    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.SNDTIMEO, timeout)
    socket.setsockopt(zmq.RCVTIMEO, timeout)
    try:
        start = perf_counter()
        socket.connect(endpoint)
        socket.send_multipart(request)
        t0 = perf_counter()
        hs, he = local["halo_start"], local["halo_end"]
        local_disp, local_mask = compute_sad(
            left[hs:he], right[hs:he], window, d_min, d_max
        )
        local_seconds = perf_counter() - t0
        t_wait = perf_counter()
        response = socket.recv_multipart()
        wait_seconds = perf_counter() - t_wait
        remote_disp, remote_mask, remote_seconds = decode_response(
            response, job_id, remote, w
        )
        full_disp, full_mask = merge_rows([
            {**local, "disparity_map": local_disp, "valid_mask": local_mask},
            {**remote, "disparity_map": remote_disp, "valid_mask": remote_mask},
        ], h, w)
        total_seconds = perf_counter() - start
        stats = {
            "total_seconds": total_seconds,
            "local_compute_seconds": local_seconds,
            "remote_compute_seconds": remote_seconds,
            "receive_wait_seconds": wait_seconds,
            "request_payload_bytes": sum(map(len, request)),
            "response_payload_bytes": sum(map(len, response)),
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
    print("T15 OK: SAD distribuido = SAD secuencial (mapa y mascara)")
    for key, value in stats.items():
        print(f"  {key}: {value:.6f}" if key.endswith("seconds") else f"  {key}: {value}")


if __name__ == "__main__":
    main()
