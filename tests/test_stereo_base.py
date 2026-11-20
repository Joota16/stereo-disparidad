import unittest
from pathlib import Path
import tempfile
import cv2
import numpy as np

from src.common.io_utils import load_stereo_pair, save_disparity_colormap
from src.stereo.sad import compute_sad


class TestStereoBase(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        self.H, self.W = 40, 60
        self.left = np.random.randint(40, 220, size=(self.H, self.W), dtype=np.uint8)
        self.right = self.left.copy()

        # Objeto desplazado d = 5
        patch = np.random.randint(10, 250, size=(10, 10), dtype=np.uint8)
        self.left[15:25, 25:35] = patch
        self.right[15:25, 20:30] = patch

    def test_compute_sad_signature_and_types(self):
        disp, mask = compute_sad(self.left, self.right, window_size=5, d_min=0, d_max=16)
        self.assertEqual(disp.shape, (self.H, self.W))
        self.assertEqual(mask.shape, (self.H, self.W))
        self.assertEqual(disp.dtype, np.float32)
        self.assertEqual(mask.dtype, bool)

    def test_synthetic_disparity_recovery(self):
        disp, mask = compute_sad(self.left, self.right, window_size=5, d_min=0, d_max=16)
        self.assertTrue(mask[20, 30])
        self.assertEqual(disp[20, 30], 5.0)

    def test_invalid_borders_are_nan(self):
        r = 7 // 2
        disp, mask = compute_sad(self.left, self.right, window_size=7, d_min=0, d_max=16)
        self.assertTrue(np.all(np.isnan(disp[:r, :])))
        self.assertTrue(np.all(~mask[:r, :]))
        self.assertTrue(np.all(np.isnan(disp[self.H - r:, :])))
        self.assertTrue(np.all(~mask[self.H - r:, :]))

    def test_tie_breaking_picks_min_disparity(self):
        left_flat = np.full((30, 30), 100, dtype=np.uint8)
        right_flat = np.full((30, 30), 100, dtype=np.uint8)
        disp, mask = compute_sad(left_flat, right_flat, window_size=5, d_min=2, d_max=10)
        self.assertTrue(mask[15, 15])
        self.assertEqual(disp[15, 15], 2.0)

    def test_io_utils_load_pair_and_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lp = Path(tmpdir) / "left.png"
            rp = Path(tmpdir) / "right.png"
            outp = Path(tmpdir) / "disp.png"

            cv2.imwrite(str(lp), self.left)
            cv2.imwrite(str(rp), self.right)

            l_loaded, r_loaded = load_stereo_pair(lp, rp)
            self.assertEqual(l_loaded.shape, self.left.shape)

            disp, mask = compute_sad(l_loaded, r_loaded, window_size=5, d_min=0, d_max=10)
            save_disparity_colormap(disp, outp, valid_mask=mask)
            self.assertTrue(outp.is_file())


if __name__ == "__main__":
    unittest.main()
