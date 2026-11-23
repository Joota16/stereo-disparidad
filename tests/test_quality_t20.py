"""Pruebas unitarias para evaluacion de calidad y conversion a profundidad (T20)."""

import numpy as np
import pytest

from experiments.evaluate_quality import disparity_to_depth, run_quality_evaluation
from src.common.metrics import evaluate_disparity


def test_disparity_to_depth_with_doffs():
    # Disparidad de 10.0 px con f=1000, B=200, doffs=50 -> Z = 200 * 1000 / (10 + 50) = 3333.333 mm
    disp = np.array([[10.0, 0.0], [-1.0, 50.0]], dtype=np.float32)
    depth = disparity_to_depth(disp, baseline_mm=200.0, focal_px=1000.0, doffs_px=50.0)

    assert depth.shape == (2, 2)
    assert np.isclose(depth[0, 0], 200000.0 / 60.0)
    assert np.isclose(depth[0, 1], 200000.0 / 50.0)  # d=0 pero doffs=50 > 0 -> valido
    assert np.isnan(depth[1, 0])  # d=-1 negativo -> invalido
    assert np.isclose(depth[1, 1], 200000.0 / 100.0)


def test_evaluate_disparity_with_inf_ground_truth():
    pred = np.full((10, 10), 5.0, dtype=np.float32)
    mask = np.ones((10, 10), dtype=bool)

    gt = np.full((10, 10), 4.5, dtype=np.float32)
    gt[0:2, :] = np.inf  # 20 pixeles ocluidos/invalidos en GT

    res = evaluate_disparity(pred, mask, gt, threshold=1.0)
    assert res["evaluated_pixels"] == 80  # 100 - 20
    assert np.isclose(res["mae"], 0.5)
    assert np.isclose(res["rmse"], 0.5)
    assert res["bad_pixel_ratio"] == 0.0


def test_incompatible_dimensions_raise_error(tmp_path):
    # Generar imagenes falsas con dimensiones incompatibles
    import cv2
    img = np.zeros((50, 50), dtype=np.uint8)
    gt = np.zeros((40, 40), dtype=np.float32)

    img_dir = tmp_path / "img"
    img_dir.mkdir()
    cv2.imwrite(str(img_dir / "im0.png"), img)
    cv2.imwrite(str(img_dir / "im1.png"), img)

    # calib.txt
    with open(img_dir / "calib.txt", "w") as f:
        f.write("baseline=100\ncam0=[1000 0 0; 0 1000 0; 0 0 1]\ndoffs=0\n")

    # Guardar PFM incompatible
    gt_file = tmp_path / "disp0.pfm"
    header = f"Pf\n40 40\n-1.0\n".encode("latin-1")
    with open(gt_file, "wb") as f:
        f.write(header)
        np.flipud(gt).astype("<f4").tofile(f)

    with pytest.raises(ValueError, match="Discrepancia de dimensiones"):
        run_quality_evaluation(data_dir=str(img_dir), gt_path=str(gt_file), out_dir=str(tmp_path / "out"))
