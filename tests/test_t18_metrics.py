"""T18: la instrumentación conserva equivalencia y genera tiempos válidos."""

import socket
import threading

import numpy as np

from src.distributed.master import run_master
from src.distributed.worker import run_worker
from src.stereo.sad import compute_sad


def test_t18_instrumentacion_y_equivalencia():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    endpoint = f"tcp://127.0.0.1:{port}"
    ready = threading.Event()
    thread = threading.Thread(
        target=run_worker,
        args=({"bind": endpoint, "max_requests": 1, "ready_event": ready},),
        daemon=True,
    )
    thread.start()
    assert ready.wait(5)

    rng = np.random.default_rng(2026)
    left = rng.integers(0, 256, size=(19, 30), dtype=np.uint8)
    right = rng.integers(0, 256, size=(19, 30), dtype=np.uint8)
    actual_map, actual_mask, stats = run_master({
        "left_gray": left, "right_gray": right,
        "window_size": 5, "d_min": 0, "d_max": 8,
        "connect": endpoint, "timeout_ms": 10000,
    })
    expected_map, expected_mask = compute_sad(left, right, 5, 0, 8)
    np.testing.assert_array_equal(actual_mask, expected_mask)
    np.testing.assert_allclose(actual_map, expected_map, rtol=0, atol=0, equal_nan=True)

    for key in (
        "total_seconds", "partition_seconds", "serialize_seconds",
        "socket_setup_seconds", "connect_call_seconds", "send_call_seconds",
        "local_compute_seconds", "receive_wait_seconds", "remote_compute_seconds",
        "response_decode_seconds", "merge_seconds",
    ):
        assert isinstance(stats[key], (float, int))
        assert stats[key] >= 0

    assert stats["total_seconds"] >= stats["local_compute_seconds"]
    assert stats["request_payload_bytes"] > 0
    assert stats["response_payload_bytes"] > 0
    thread.join(timeout=5)
    assert not thread.is_alive()
