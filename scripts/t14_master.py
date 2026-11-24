
"""Emisor ZeroMQ para prueba de conexion."""

import argparse
import json

import numpy as np
import zmq


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--connect", default="tcp://127.0.0.1:5555"
    )
    args = parser.parse_args()

    left = np.arange(
        48, dtype=np.uint8
    ).reshape(6, 8)

    right = np.fliplr(left).copy()

    metadata = {
        "version": 1,
        "job_id": "t14-smoke-001",
        "height": 6,
        "width": 8,
        "dtype": "uint8",
    }

    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.SNDTIMEO, 15000)
    socket.setsockopt(zmq.RCVTIMEO, 15000)

    try:
        socket.connect(args.connect)

        socket.send_multipart([
            json.dumps(metadata).encode("utf-8"),
            left.tobytes(),
            right.tobytes(),
        ])

        frames = socket.recv_multipart()

        if len(frames) != 2:
            raise ValueError("Respuesta malformada")

        response = json.loads(frames[0].decode("utf-8"))

        if response.get("status") != "ok":
            raise RuntimeError(
                response.get("message", "Error remoto")
            )

        if (
            response.get("job_id") != metadata["job_id"]
            or response.get("height") != 6
            or response.get("width") != 8
            or response.get("dtype") != "<i2"
        ):
            raise ValueError("Metadatos inconsistentes")

        if len(frames[1]) != 6 * 8 * 2:
            raise ValueError("Longitud de respuesta incorrecta")

        remote_result = np.frombuffer(
            frames[1], dtype="<i2"
        ).reshape(6, 8)

        expected = (
            left.astype(np.int16) - right.astype(np.int16)
        )

        np.testing.assert_array_equal(
            remote_result, expected
        )

        print(
            "OK: matrices enviadas "
            "y resultado remoto validado."
        )
        print("Forma:", remote_result.shape)
        print("Tipo:", remote_result.dtype)
        print("Bytes del resultado:", len(frames[1]))

    except zmq.Again:
        raise SystemExit(
            "Sin respuesta en 15 s. "
            "Revisar IP, puerto y firewall."
        )

    finally:
        socket.close()
        context.term()


if __name__ == "__main__":
    main()
