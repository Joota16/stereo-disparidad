"""Pruebas unitarias para el runner del benchmark automatizado (T19)."""

import socket
import threading
from pathlib import Path
import numpy as np
import pytest

from experiments.run_benchmark_grid import execute_mode, run_benchmark_grid, get_environment_metadata
from src.distributed.worker import run_worker


def test_metadata_extraction():
    meta = get_environment_metadata()
    assert "platform" in meta
    assert "numpy_version" in meta
    assert "python_version" in meta


def test_execute_modes_consistency_and_t18_stats():
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

    disp_seq, mask_seq, t_seq, stats_seq = execute_mode("secuencial", left, right, 5, 0, 8)
    disp_p2, mask_p2, t_p2, stats_p2 = execute_mode("multiproceso_p2", left, right, 5, 0, 8)
    disp_dist, mask_dist, t_dist, stats_dist = execute_mode("distribuido", left, right, 5, 0, 8, endpoint=endpoint)

    assert np.array_equal(mask_seq, mask_p2)
    assert np.array_equal(mask_seq, mask_dist)
    np.testing.assert_allclose(disp_seq, disp_p2, atol=0.0, rtol=0.0, equal_nan=True)
    np.testing.assert_allclose(disp_seq, disp_dist, atol=0.0, rtol=0.0, equal_nan=True)

    # Verificar metricas de T18
    assert stats_dist is not None
    assert "partition_seconds" in stats_dist
    assert "local_compute_seconds" in stats_dist
    assert "remote_compute_seconds" in stats_dist
    assert "request_payload_bytes" in stats_dist
    th.join(timeout=3.0)


def test_benchmark_grid_csv_outputs(tmp_path):
    rng = np.random.default_rng(42)
    l = rng.integers(0, 256, size=(20, 30), dtype=np.uint8)
    r = np.roll(l, -2, axis=1)

    grid = [{"name": "TestSmall", "K": 3, "d_min": 0, "d_max": 4, "left": l, "right": r}]
    runs_csv = tmp_path / "test_runs.csv"
    summary_csv = tmp_path / "test_summary.csv"

    runs, summary = run_benchmark_grid(
        grid_configs=grid,
        modes=["secuencial", "multiproceso_p2"],
        reps=2,
        warmup=1,
        output_runs_csv=str(runs_csv),
        output_summary_csv=str(summary_csv),
    )

    assert runs_csv.exists()
    assert summary_csv.exists()
    assert len(runs) == 2 * (1 + 2)  # 2 modos * (1 warmup + 2 reps) = 6 corridas
    assert len(summary) == 2  # 2 modos

    # Verificar campos requeridos en resumen
    s_seq = next(s for s in summary if s["modalidad"] == "secuencial")
    s_p2 = next(s for s in summary if s["modalidad"] == "multiproceso_p2")
    assert s_seq["speedup"] == 1.0
    assert s_seq["eficiencia_local"] == 1.0
    assert s_p2["speedup"] > 0
    assert isinstance(s_p2["eficiencia_local"], (int, float))


def test_invalid_arguments_rejected():
    with pytest.raises(ValueError, match="repeticiones debe ser >= 1"):
        run_benchmark_grid([], [], reps=0)
    with pytest.raises(ValueError, match="calentamientos debe ser >= 0"):
        run_benchmark_grid([], [], warmup=-1)
