
"""T14: receptor ZeroMQ de prueba. No ejecuta SAD."""

import argparse
import json

import numpy as np
import zmq


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bind", default="tcp://127.0.0.1:5555"
    )
    args = parser.parse_args()

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.LINGER, 0)

    try:
        socket.bind(args.bind)
        print(f"Trabajador escuchando en {args.bind}", flush=True)

        frames = socket.recv_multipart()

        try:
            if len(frames) != 3:
                raise ValueError("Se esperan metadatos y dos matrices")

            metadata = json.loads(frames[0].decode("utf-8"))

            if metadata.get("version") != 1 or metadata.get("dtype") != "uint8":
                raise ValueError("Version o tipo no admitido")

            h = metadata["height"]
            w = metadata["width"]

            if (
                type(h) is not int
                or type(w) is not int
                or not (1 <= h <= 4096 and 1 <= w <= 4096)
            ):
                raise ValueError("Dimensiones invalidas")

            if len(frames[1]) != h * w or len(frames[2]) != h * w:
                raise ValueError("Longitud incorrecta")

            left = np.frombuffer(
                frames[1], dtype=np.uint8
            ).reshape(h, w)

            right = np.frombuffer(
                frames[2], dtype=np.uint8
            ).reshape(h, w)

            # Operacion de prueba, NO algoritmo SAD.
            result = (
                left.astype(np.int16) - right.astype(np.int16)
            ).astype("<i2")

            response = {
                "version": 1,
                "job_id": metadata["job_id"],
                "status": "ok",
                "height": h,
                "width": w,
                "dtype": "<i2",
            }

            socket.send_multipart([
                json.dumps(response).encode("utf-8"),
                result.tobytes()
            ])

            print("Solicitud procesada y resultado enviado.")

        except (ValueError, KeyError, TypeError) as exc:
            socket.send_multipart([
                json.dumps({
                    "status": "error",
                    "message": str(exc)
                }).encode("utf-8"),
                b""
            ])
            print(f"Solicitud rechazada: {exc}")

    finally:
        socket.close()
        context.term()


if __name__ == "__main__":
    main()
