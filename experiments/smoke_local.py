
"""Prueba exploratoria de rendimiento SAD local."""

from statistics import median
from time import perf_counter

import numpy as np

from src.stereo.sad import compute_sad
from src.parallel.multiprocess import compute_disparity_parallel


def main():
    rng = np.random.default_rng(2026)

    left = rng.integers(
        0, 256, size=(96, 160), dtype=np.uint8
    )
    right = rng.integers(
        0, 256, size=(96, 160), dtype=np.uint8
    )

    params = (5, 0, 8)

    reference_map, reference_mask = compute_sad(
        left, right, *params
    )

    results = {}

    for workers in [1, 2, 4]:
        times = []

        for _ in range(3):
            start = perf_counter()

            disparity, mask = compute_disparity_parallel(
                left, right, *params, workers
            )

            elapsed = perf_counter() - start

            np.testing.assert_array_equal(
                mask, reference_mask
            )
            np.testing.assert_allclose(
                disparity, reference_map,
                rtol=0, atol=0, equal_nan=True
            )

            times.append(elapsed)

        results[workers] = median(times)

    baseline = results[1]

    print("\nRESULTADOS EXPLORATORIOS")
    print("-----------------------")

    for workers, elapsed in results.items():
        speedup = baseline / elapsed
        print(
            f"{workers} proceso(s): "
            f"{elapsed:.4f} s | "
            f"Speedup: {speedup:.3f}x"
        )


if __name__ == "__main__":
    main()
