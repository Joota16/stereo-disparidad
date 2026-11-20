import unittest
import numpy as np

from src.common.metrics import evaluate_disparity, compute_error_map


class TestDisparityMetrics(unittest.TestCase):
    def setUp(self):
        self.H, self.W = 10, 10
        # Mapa estimado
        self.pred = np.full((self.H, self.W), 5.0, dtype=np.float32)
        self.valid_mask = np.ones((self.H, self.W), dtype=bool)

        # Ground truth identico
        self.gt = np.full((self.H, self.W), 5.0, dtype=np.float32)

    def test_perfect_match_metrics(self):
        metrics = evaluate_disparity(self.pred, self.valid_mask, self.gt)
        self.assertEqual(metrics["mae"], 0.0)
        self.assertEqual(metrics["rmse"], 0.0)
        self.assertEqual(metrics["bad_pixel_ratio"], 0.0)
        self.assertEqual(metrics["invalid_ratio"], 0.0)
        self.assertEqual(metrics["evaluated_pixels"], 100)

    def test_known_error_metrics(self):
        # 10 pixeles con error = 2.0 (supera umbral 1.0)
        self.pred[0, :10] = 7.0
        # 90 pixeles con error = 0.0
        metrics = evaluate_disparity(self.pred, self.valid_mask, self.gt, threshold=1.0)

        # MAE esperado: (10 * 2.0 + 90 * 0) / 100 = 0.2
        self.assertAlmostEqual(metrics["mae"], 0.2)
        # RMSE esperado: sqrt((10 * 4.0 + 90 * 0) / 100) = sqrt(0.4) = 0.63245
        self.assertAlmostEqual(metrics["rmse"], np.sqrt(0.4), places=4)
        # Bad-Pixel Ratio esperado: 10%
        self.assertEqual(metrics["bad_pixel_ratio"], 10.0)

    def test_ignores_non_finite_gt(self):
        # Pixeles infinitos u ocluidos en la referencia
        self.gt[0, 0] = np.inf
        self.gt[0, 1] = np.nan
        metrics = evaluate_disparity(self.pred, self.valid_mask, self.gt)

        self.assertEqual(metrics["evaluated_pixels"], 98)

    def test_error_map_shape_and_nans(self):
        self.valid_mask[5:, :] = False
        metrics = evaluate_disparity(self.pred, self.valid_mask, self.gt)
        err_map = metrics["error_map"]

        self.assertEqual(err_map.shape, (self.H, self.W))
        self.assertTrue(np.all(np.isnan(err_map[5:, :])))
        self.assertTrue(np.all(~np.isnan(err_map[:5, :])))


if __name__ == "__main__":
    unittest.main()
