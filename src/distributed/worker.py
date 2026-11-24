"""Trabajador ZeroMQ para computar SAD sobre franjas con halos."""

import argparse
from time import perf_counter

import zmq

from src.distributed.protocol import decode_request, encode_response, encode_error
from src.stereo.sad import compute_sad


def run_worker(config):
    endpoint = config.get("bind", "tcp://127.0.0.1:5555")
    max_requests = config.get("max_requests")  # None = servicio continuo
    ready_event = config.get("ready_event")
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.LINGER, 0)
    handled = 0
    try:
        socket.bind(endpoint)
        if ready_event is not None:
            ready_event.set()
        print(f"Trabajador SAD escuchando en {endpoint}", flush=True)
        while max_requests is None or handled < max_requests:
            frames = socket.recv_multipart()
            try:
                meta, left, right = decode_request(frames)
                begin = perf_counter()
                disp, mask = compute_sad(
                    left, right, meta["window_size"], meta["d_min"], meta["d_max"]
                )
                seconds = perf_counter() - begin
                reply = encode_response(meta, disp, mask, seconds)
                print(f"Job {meta['job_id']} OK: {seconds:.4f} s", flush=True)
            except (Exception) as exc:
                reply = encode_error(exc)
                print(f"Solicitud rechazada: {exc}", flush=True)
            socket.send_multipart(reply)
            handled += 1
    finally:
        socket.close()
        context.term()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="tcp://127.0.0.1:5555")
    parser.add_argument("--once", action="store_true", help="Procesar una solicitud y salir")
    args = parser.parse_args()
    try:
        run_worker({"bind": args.bind, "max_requests": 1 if args.once else None})
    except KeyboardInterrupt:
        print("Trabajador detenido")


if __name__ == "__main__":
    main()
