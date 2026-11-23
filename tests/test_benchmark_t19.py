"""Pruebas unitarias para el runner del benchmark automatizado (T19)."""

import socket
import threading
import numpy as np
import pytest

from experiments.run_benchmark_grid import execute_mode, run_benchmark_cell
from src.distributed.worker import run_worker


def test_execute_modes_consistency():
    rng = np.random.default_rng(123)
    left = rng.integers(0, 256, size=(30, 40), dtype=np.uint8)
    right = np.roll(left, -3, axis=1)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    endpoint = f"tcp://127.0.0.1:{port}"

    ready = threading.Event()
    th = threading.Thread(target=run_worker, args=({"bind": endpoint, "max_requests": 1, "ready_event": ready},), daemon=True)
    th.start()
    assert ready.wait(timeout=5.0)

    # Correr secuencial
    disp_seq, mask_seq, t_seq = execute_mode("secuencial", left, right, 5, 0, 8)
    # Correr paralelo 2
    disp_p2, mask_p2, t_p2 = execute_mode("multiproceso_p2", left, right, 5, 0, 8)
    # Correr distribuido
    disp_dist, mask_dist, t_dist = execute_mode("distribuido_zmq", left, right, 5, 0, 8, endpoint=endpoint)

    assert np.array_equal(mask_seq, mask_p2)
    assert np.array_equal(mask_seq, mask_dist)
    np.testing.assert_allclose(disp_seq, disp_p2, atol=0.0, rtol=0.0, equal_nan=True)
    np.testing.assert_allclose(disp_seq, disp_dist, atol=0.0, rtol=0.0, equal_nan=True)
    assert t_seq > 0
    assert t_p2 > 0
    assert t_dist > 0
    th.join(timeout=3.0)
