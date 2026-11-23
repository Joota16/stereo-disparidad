"""Pruebas de regresion para las correcciones de T19 y T20."""

import numpy as np
import pytest

from experiments.evaluate_quality import ground_truth_range_coverage
from experiments.run_benchmark_grid import run_benchmark_grid


def test_coverage_uses_pixel_distribution_not_interval():
    gt = np.array([[10, 10, 10, 20, 30, np.inf, np.nan, -1]], dtype=np.float32)
    assert ground_truth_range_coverage(gt, 0, 15) == pytest.approx(60.0)
    assert ground_truth_range_coverage(gt, 0, 32) == pytest.approx(100.0)


def test_coverage_rejects_invalid_ground_truth():
    with pytest.raises(ValueError, match="sin pixeles"):
        ground_truth_range_coverage(np.array([np.inf, -5], dtype=np.float32), 0, 32)


def test_t19_rejects_non_equivalent_computations(tmp_path, monkeypatch):
    import experiments.run_benchmark_grid as module
    from src.stereo.sad import compute_sad

    left = np.zeros((12, 16), dtype=np.uint8)
    right = np.zeros_like(left)

    def fake_execute(mode, l, r, k, dmin, dmax, endpoint=None):
        disp, mask = compute_sad(l, r, k, dmin, dmax)
        if mode == "multiproceso_p2":
            disp[mask] += 1
        return disp, mask, 0.01, None

    monkeypatch.setattr(module, "execute_mode", fake_execute)
    cfg = [{"name": "small", "left": left, "right": right,
            "K": 3, "d_min": 0, "d_max": 4}]
    with pytest.raises(AssertionError, match="Fallo equivalencia"):
        run_benchmark_grid(
            cfg, ["secuencial", "multiproceso_p2"], reps=1, warmup=0,
            output_runs_csv=str(tmp_path / "runs.csv"),
            output_summary_csv=str(tmp_path / "summary.csv"))


def test_t19_does_not_overwrite_previous_evidence(tmp_path):
    left = np.zeros((10, 15), dtype=np.uint8)
    cfg = [{"name": "small", "left": left, "right": left.copy(),
            "K": 3, "d_min": 0, "d_max": 4}]
    args = dict(grid_configs=cfg, modes=["secuencial"], reps=1, warmup=0,
                output_runs_csv=str(tmp_path / "newdir" / "runs.csv"),
                output_summary_csv=str(tmp_path / "newdir" / "summary.csv"))
    run_benchmark_grid(**args)
    assert (tmp_path / "newdir" / "runs_metadata.json").exists()
    with pytest.raises(FileExistsError):
        run_benchmark_grid(**args)
    run_benchmark_grid(**args, overwrite=True)
