"""T18: control de costo ZeroMQ sin computo SAD.

Mantiene el formato binario de la solicitud y respuesta SAD real, pero la
laptop genera un mapa vacio en lugar de calcular SAD.
No estima latencia pura de red: incluye trabajo de protocolo y sockets.
"""

import argparse
import csv
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import uuid4

import numpy as np
import zmq

from src.distributed.protocol import (
    decode_request,
    decode_response,
    encode_error,
    encode_request,
    encode_response,
)
from src.parallel.partition import split_rows


def run_echo_worker(bind, max_requests=None, ready_event=None):
    context = zmq.Context()
    sock = context.socket(zmq.REP)
    sock.setsockopt(zmq.LINGER, 0)
    count = 0
    try:
        sock.bind(bind)
        if ready_event is not None:
            ready_event.set()
        print(f"T18 control SIN SAD: trabajador escuchando en {bind}", flush=True)
        while max_requests is None or count < max_requests:
            frames = sock.recv_multipart()
            try:
                meta, _left, _right = decode_request(frames)
                h, w = meta["shape"]
                # Mismo tamano/formato de respuesta que SAD, sin calculo.
                empty_map = np.full((h, w), np.nan, dtype=np.float32)
                empty_mask = np.zeros((h, w), dtype=bool)
                reply = encode_response(meta, empty_map, empty_mask, 0.0)
            except (ValueError, TypeError, KeyError) as exc:
                reply = encode_error(str(exc))
            sock.send_multipart(reply)
            count += 1
    finally:
        sock.close()
        context.term()
    return count


def measure_roundtrip(connect, height=192, width=320,
                      repetitions=30, warmups=5, timeout_ms=15000):
    if height < 2 or width < 1 or repetitions < 1 or warmups < 0:
        raise ValueError("Altura >= 2, ancho >= 1, repeticiones >= 1, warmups >= 0")
    rng = np.random.default_rng(2026)
    left = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
    right = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
    remote = split_rows(height, 2, 5)[1]
    hs, he = remote["halo_start"], remote["halo_end"]
    left_part, right_part = left[hs:he], right[hs:he]
    measured = []

    for i in range(warmups + repetitions):
        job_id = uuid4().hex
        start = perf_counter()
        request = encode_request(remote, left_part, right_part, height,
                                 5, 0, 8, job_id)
        context = zmq.Context()
        sock = context.socket(zmq.REQ)
        sock.setsockopt(zmq.LINGER, 0)
        sock.setsockopt(zmq.SNDTIMEO, timeout_ms)
        sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
        try:
            sock.connect(connect)
            sock.send_multipart(request)
            response = sock.recv_multipart()
            disparity, mask, compute_seconds = decode_response(
                response, job_id, remote, width
            )
            if np.any(mask) or not np.all(np.isnan(disparity)) or compute_seconds != 0:
                raise ValueError("Respuesta del control SIN SAD no corresponde")
        except zmq.Again as exc:
            raise TimeoutError(
                "Control ZeroMQ sin respuesta. Revisar worker, IP y puerto."
            ) from exc
        finally:
            sock.close()
            context.term()
        elapsed = perf_counter() - start
        if i >= warmups:
            measured.append({
                "repetition": i - warmups + 1,
                "height": height,
                "width": width,
                "roundtrip_seconds": elapsed,
                "request_payload_bytes": sum(map(len, request)),
                "response_payload_bytes": sum(map(len, response)),
            })
    return measured


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("worker", "master"), required=True)
    parser.add_argument("--bind", default="tcp://127.0.0.1:5555")
    parser.add_argument("--connect", default="tcp://127.0.0.1:5555")
    parser.add_argument("--height", type=int, default=192)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--reps", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--output", default="results/t18_roundtrip_192x320.csv")
    args = parser.parse_args()

    if args.role == "worker":
        try:
            run_echo_worker(args.bind)
        except KeyboardInterrupt:
            print("Control T18 detenido")
        return

    results = measure_roundtrip(
        args.connect, args.height, args.width, args.reps, args.warmups
    )
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

    times = [r["roundtrip_seconds"] for r in results]
    print(f"Control ZeroMQ SIN SAD ({args.height} x {args.width})")
    print(f"Repeticiones: {len(times)}; warmups descartados: {args.warmups}")
    print(f"Mediana: {median(times):.6f} s")
    print(f"Minimo: {min(times):.6f} s; maximo: {max(times):.6f} s")
    print(f"Solicitud: {results[0]['request_payload_bytes']} B")
    print(f"Respuesta: {results[0]['response_payload_bytes']} B")
    print("No es latencia pura de red; incluye sockets y protocolo en ambos nodos.")
    print(f"CSV: {path}")


if __name__ == "__main__":
    main()
