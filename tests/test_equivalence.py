import unittest
import numpy as np

from src.stereo.sad import compute_sad
from src.parallel.multiprocess import compute_disparity_parallel


class TestEquivalenceT13(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        self.H, self.W = 35, 45
        self.left = np.random.randint(40, 220, size=(self.H, self.W), dtype=np.uint8)
        self.right = self.left.copy()
        # Desplazamiento sintetico d = 4
        self.right[10:25, 10:30] = self.left[10:25, 14:34]

    def test_strict_numerical_equivalence_multiprocess(self):
        for window_size in (3, 5):
            for d_max in (8, 12):
                disp_seq, mask_seq = compute_sad(self.left, self.right, window_size, 0, d_max)

                for workers in (2, 3, 4):
                    disp_par, mask_par = compute_disparity_parallel(
                        self.left, self.right, window_size, 0, d_max, workers
                    )

                    # 1. Mascaras identicas
                    np.testing.assert_array_equal(mask_seq, mask_par)

                    # 2. En pixeles validos, la diferencia debe ser exactamente 0.0
                    valid = mask_seq & mask_par
                    np.testing.assert_array_equal(disp_seq[valid], disp_par[valid])

                    # 3. En pixeles invalidos, ambos deben ser NaN
                    self.assertTrue(np.all(np.isnan(disp_seq[~mask_seq])))
                    self.assertTrue(np.all(np.isnan(disp_par[~mask_par])))


if __name__ == "__main__":
    unittest.main()
