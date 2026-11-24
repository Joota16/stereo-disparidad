"""Pruebas unitarias para comunicacion distribuida y loopback."""

import socket
import threading

import numpy as np
import pytest

from src.distributed.master import run_master
from src.distributed.worker import run_worker
from src.distributed.protocol import encode_request, decode_request, encode_error, decode_response
from src.parallel.partition import split_rows
from src.stereo.sad import compute_sad


def test_roundtrip_request_binario():
    left = np.arange(42, dtype=np.uint8).reshape(6, 7)
    right = np.fliplr(left).copy()
    part = {"worker_id": 1, "row_start": 2, "row_end": 5, "halo_start": 0, "halo_end": 6}
    frames = encode_request(part, left, right, 6, 3, 0, 4, "test")
    meta, actual_left, actual_right = decode_request(frames)
    assert meta["part"] == part
    np.testing.assert_array_equal(actual_left, left)
    np.testing.assert_array_equal(actual_right, right)


def test_solicitud_truncada_rechazada():
    left = np.arange(42, dtype=np.uint8).reshape(6, 7)
    part = {"worker_id": 1, "row_start": 2, "row_end": 5, "halo_start": 0, "halo_end": 6}
    frames = encode_request(part, left, left, 6, 3, 0, 4, "test")
    frames[1] = frames[1][:-1]
    with pytest.raises(ValueError):
        decode_request(frames)


def test_error_remoto_se_propaga():
    part = {"worker_id": 1, "row_start": 2, "row_end": 5, "halo_start": 0, "halo_end": 6}
    with pytest.raises(RuntimeError, match="Error remoto"):
        decode_response(encode_error("error prueba"), "test", part, 7)


@pytest.mark.parametrize("height,width,window,d_min,d_max", [
    (21, 29, 3, 0, 8),
    (19, 30, 5, 2, 11),
    (7, 10, 7, 0, 6),
])
def test_integracion_loopback(height, width, window, d_min, d_max):
    # Escoger un puerto temporal libre en loopback; la prueba es local, no utiliza la laptop.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    endpoint = f"tcp://127.0.0.1:{port}"
    ready = threading.Event()
    worker = threading.Thread(target=run_worker, args=({
        "bind": endpoint, "max_requests": 1, "ready_event": ready,
    },), daemon=True)
    worker.start()
    assert ready.wait(5), "Worker no inicio"
    rng = np.random.default_rng(2026)
    left = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
    right = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
    distributed_map, distributed_mask, stats = run_master({
        "left_gray": left, "right_gray": right, "connect": endpoint,
        "window_size": window, "d_min": d_min, "d_max": d_max, "timeout_ms": 10000,
    })
    serial_map, serial_mask = compute_sad(left, right, window, d_min, d_max)
    np.testing.assert_array_equal(distributed_mask, serial_mask)
    np.testing.assert_allclose(distributed_map, serial_map, atol=0, rtol=0, equal_nan=True)
    assert stats["request_payload_bytes"] > 0
    assert stats["response_payload_bytes"] > 0
    worker.join(timeout=5)
    assert not worker.is_alive()
