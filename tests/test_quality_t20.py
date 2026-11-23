"""Pruebas unitarias para evaluacion de calidad y conversion a profundidad (T20)."""

import numpy as np
import pytest

from experiments.evaluate_quality import disparity_to_depth
from src.common.metrics import evaluate_disparity


def test_disparity_to_depth_conversion():
    # Disparidad de 10.0 px con f=1000, B=200, doffs=0 -> Z = 200 * 1000 / 10 = 20,000 mm (20 metros)
    disp = np.array([[10.0, 20.0], [0.0, -5.0]], dtype=np.float32)
    depth = disparity_to_depth(disp, baseline_mm=200.0, focal_px=1000.0, doffs_px=0.0)

    assert depth.shape == (2, 2)
    assert np.isclose(depth[0, 0], 20000.0)
    assert np.isclose(depth[0, 1], 10000.0)
    assert np.isnan(depth[1, 0])  # disparidad 0 es invalida
    assert np.isnan(depth[1, 1])  # disparidad negativa es invalida


def test_evaluate_disparity_synthetic():
    pred = np.full((10, 10), 5.0, dtype=np.float32)
    mask = np.ones((10, 10), dtype=bool)
    gt = np.full((10, 10), 4.5, dtype=np.float32)

    res = evaluate_disparity(pred, mask, gt, threshold=1.0)
    assert np.isclose(res["mae"], 0.5)
    assert np.isclose(res["rmse"], 0.5)
    assert res["bad_pixel_ratio"] == 0.0  # error 0.5 <= umbral 1.0
    assert res["invalid_ratio"] == 0.0
