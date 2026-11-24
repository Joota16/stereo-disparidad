"""Pruebas de equivalencia numerica distribuida vs secuencial."""

import socket
import threading
import numpy as np
import pytest

from src.distributed.master import run_master
from src.distributed.worker import run_worker
from src.stereo.sad import compute_sad


@pytest.mark.parametrize("h,w,window,d_min,d_max", [
    (35, 45, 5, 0, 10),
    (41, 55, 7, 0, 8),
    (50, 60, 3, 2, 12),
])
def test_distributed_vs_sequential_exact_equivalence(h, w, window, d_min, d_max):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    endpoint = f"tcp://127.0.0.1:{port}"

    ready = threading.Event()
    worker = threading.Thread(
        target=run_worker,
        args=({"bind": endpoint, "max_requests": 1, "ready_event": ready},),
        daemon=True,
    )
    worker.start()
    assert ready.wait(timeout=5.0), "El trabajador distribuido no inicio a tiempo"

    rng = np.random.default_rng(42)
    left = rng.integers(0, 256, size=(h, w), dtype=np.uint8)
    right = rng.integers(0, 256, size=(h, w), dtype=np.uint8)

    disp_dist, mask_dist, stats = run_master({
        "left_gray": left,
        "right_gray": right,
        "window_size": window,
        "d_min": d_min,
        "d_max": d_max,
        "connect": endpoint,
        "timeout_ms": 10000,
    })

    disp_seq, mask_seq = compute_sad(left, right, window, d_min, d_max)

    # 1. Mascara de validez identica
    np.testing.assert_array_equal(mask_dist, mask_seq)

    # 2. Disparidades exactamente identicas (tolerancia cero absoluto)
    np.testing.assert_allclose(disp_dist, disp_seq, atol=0.0, rtol=0.0, equal_nan=True)

    worker.join(timeout=3.0)
    assert not worker.is_alive()
