
import numpy as np
import pytest

from src.stereo.sad import compute_sad
from src.parallel.multiprocess import compute_disparity_parallel


@pytest.mark.parametrize("workers", [1, 2, 4])
@pytest.mark.parametrize("window_size", [3, 5])
def test_equivalencia_sad(workers, window_size):
    rng = np.random.default_rng(2026)

    left = rng.integers(
        0, 256, size=(21, 29), dtype=np.uint8
    )
    right = rng.integers(
        0, 256, size=(21, 29), dtype=np.uint8
    )

    expected_map, expected_mask = compute_sad(
        left, right, window_size, 0, 8
    )

    actual_map, actual_mask = compute_disparity_parallel(
        left, right, window_size, 0, 8, workers
    )

    np.testing.assert_array_equal(
        actual_mask, expected_mask
    )

    np.testing.assert_allclose(
        actual_map,
        expected_map,
        rtol=0,
        atol=0,
        equal_nan=True,
    )


def test_rechaza_dimensiones_diferentes():
    left = np.zeros((10, 12), dtype=np.uint8)
    right = np.zeros((10, 11), dtype=np.uint8)

    with pytest.raises(ValueError):
        compute_disparity_parallel(
            left, right, 3, 0, 4, 2
        )


def test_rechaza_trabajadores_excesivos():
    left = np.zeros((3, 12), dtype=np.uint8)

    with pytest.raises(ValueError):
        compute_disparity_parallel(
            left, left, 3, 0, 4, 4
        )
